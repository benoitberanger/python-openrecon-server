#!/bin/python3

import base64
import gc
import logging
import os
import subprocess
import xml

import ismrmrd
import numpy as np

from converter.mrd2nifti import nifti_from_image_array
from converter.nifti2mrd import images_from_nifti
from utils.OutputSeries import OutputSeries, ProcessImageResult
from utils.check_OR_arguments import check_OR_arguments
from utils.img_array import flatten, get_type_magnitude, get_subarray, mrd_indexes, stack_images
from utils.memory import log_memory, log_memory_delta
from utils.utils import display_diagnostic, normalise


# Folder for debug output files
debugFolder = "/tmp/share/debug"

# Folder for NIfTI files from ROMEO results 
niftiFolder = "/tmp/share/romeo"

def process_image(img_array: np.ndarray[ismrmrd.Image], configJSON: dict | None, metadata) -> ProcessImageResult:
    """
    Invert contrast process image.

    Parameters
    ----------
    img_array : np.ndarray
        nD MRD image array [slice, contrast, average, phase,
        repetition, set, image_type] as returned by build_image_array().
    configJSON : dict or None
        JSON configuration from the client.
    metadata : ismrmrd.xsd.ismrmrdHeader or str
        MRD header.

    Returns
    -------
    list of tuple (np.ndarray, list of ismrmrd.ImageHeader, list of ismrmrd.Meta)
        One tuple per image type present in the dataset, in the order
        they were encountered. Each data array has shape
        [img, cha, z, y, x], dtype int16
    """
    
    # Create debug folder, if necessary
    if not os.path.exists(debugFolder):
        os.makedirs(debugFolder)
        logging.debug("Created folder " + debugFolder + " for debug output files")
    
    # Create nifti folder, if necessary
    if not os.path.exists(niftiFolder):
        os.makedirs(niftiFolder)
        logging.debug("Created folder " + niftiFolder + " for ROMEO nifti output files")

    logging.info(f'------------------------------------------------')
    logging.info(f'     ROMEO called')
    logging.info(f'------------------------------------------------')
    
    mem = log_memory("process_image", "Begining")
    
    BitsStored = 12
    maxVal = 2**BitsStored - 1

    # --- Dimensions ------------------------------------------------------
    # Get the number of image_type (img_array axis 6)
    n_image_type = img_array.shape[mrd_indexes.image_type]
    image_type_name = ('', 'MAGNITUDE', 'PHASE', 'REAL', 'IMAG', 'COMPLEX', 'RGB')

    # --- Treat all types of images ---------------------------------------
    series = OutputSeries()
    nifti_M = None
    nifti_P = None
    echo_times = []
    
    for serie_index in range(0, img_array.shape[mrd_indexes.image_series_index]):

        logging.debug(f"Series index : {serie_index}")
        # get Magnitude image
        mag_array = get_subarray(img_array, img_image_type=ismrmrd.IMTYPE_MAGNITUDE, img_image_series_index=serie_index)
        if mag_array.any():
            nifti_M = nifti_from_image_array(mag_array, "/tmp/share/romeo", ["contrast"])
            # --- stack images ------------------------------------------------
            mag_images = flatten(mag_array)
            _, _, meta = stack_images(mag_images)
            tmp_echo = [float(m.get("EchoTime")) for m in meta]
            echo_times = np.unique(tmp_echo).tolist()
            mem = log_memory_delta("process_image", "After stack_images", mem)
            del mag_array, mag_images

        # get Phase image
        phase_array = get_subarray(img_array, img_image_type=ismrmrd.IMTYPE_PHASE, img_image_series_index=serie_index)
        if phase_array.any():
            phase_template = flatten(phase_array)
            nifti_P = nifti_from_image_array(phase_array, "/tmp/share/romeo", ["contrast"])
            # --- stack images ------------------------------------------------
            _, _, meta = stack_images(phase_template)
            tmp_echo = [float(m.get("EchoTime")) for m in meta]
            echo_times = np.unique(tmp_echo).tolist()
            mem = log_memory_delta("process_image", "After stack_images", mem)
            del phase_array
        
        if not nifti_P :
            continue

        logging.info(f"TE = {echo_times}")
        run_ROMEO(nifti_P, nifti_M, echo_times)

        unwrapped_path = os.path.join(niftiFolder, "unwrapped.nii")
        if len(echo_times) > 1:
            unwrapped_images = images_from_nifti(unwrapped_path, phase_template, ["contrast"])
        else :
            unwrapped_images = images_from_nifti(unwrapped_path, phase_template)
        data, head, meta = images_to_triplet(unwrapped_images)

        del unwrapped_images

        # # --- Normalise to 12-bit range and convert to int16 --------------
        # data = normalise(data)
        # data = data.astype(np.int16)
        # gc.collect()
        # mem = log_memory_delta("process_image", "After normalisation", mem)

        data_min = np.nanmin(data)
        data_shifted = (data - data_min).astype(np.uint16)

        for m in meta:
            m["RescaleSlope"]     = "1"
            m["RescaleIntercept"] = str(int(data_min))

        series.add(data_shifted, head, meta,
                process_history=["PYTHON", "ROMEO Unwrapping"],
                sequence_description="ROMEO")
        del data, data_shifted
        gc.collect()
        mem = log_memory_delta("process_image", "After series.add", mem)
        nifti_P = None

    if series is None:
        logging.error("No images found in img_array. Returning empty result.")
        return []
    
    log_memory_delta("process_image", "End", mem)
    logging.info("--- End of ROMEO ---------------------")
    return series.get()


def run_ROMEO(nifti_path_P: str, nifti_path_M: str = None, echo_times: list = []):

    cmd = ["julia", "/opt/romeo/romeo.jl",  "-v", "--compute-B0", "-o", niftiFolder, "-p", nifti_path_P]
    # cmd = ["julia", "/opt/romeo/romeo.jl", "-o", niftiFolder, "-p", nifti_path_P]
    if nifti_path_M is not None:
        cmd += ["-m", str(nifti_path_M)]
    if len(echo_times) > 1:
        cmd += ["-t", str(echo_times)]

    logging.info(f"running ROMEO unwrapping algorithm : {cmd}")
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    logging.debug(f"ROMEO: {result.stdout}")
    if result.stderr:
        logging.debug(f"ROMEO: {result.stderr}")
    # default output is "unwrapped.nii"
    

def images_to_triplet(images: list[ismrmrd.Image]) -> tuple[np.ndarray, list, list]:
    """
    Pack a flat list of already-2D ismrmrd.Image objects into the
    (data, head, meta) triplet expected by OutputSeries.add /
    send_volume_as_2Dslices, WITHOUT merging slices into a z-stack.

    Unlike stack_images (which assembles a genuine 3D/4D volume by
    stacking slices along z), this keeps every image separate on a
    new leading "img" axis, preserving z=1 per image - required since
    send_volume_as_2Dslices iterates over axis 0 expecting one already
    complete 2D image per index.

    Parameters
    ----------
    images : list of ismrmrd.Image
        Images to pack. Each must already have 
        data.shape == (cha, 1, y, x).

    Returns
    -------
    data : np.ndarray
        Shape [img, cha, 1, y, x].
    head : list of ismrmrd.ImageHeader
    meta : list of ismrmrd.Meta
    """
    for img in images:
        if img.data.shape[1] != 1:
            raise ValueError(
                f"images_to_triplet: expected z=1 per image, got "
                f"shape {img.data.shape}."
            )

    data = np.stack([np.ascontiguousarray(img.data) for img in images], axis=0)
    head = [img.getHead() for img in images]
    meta = [ismrmrd.Meta.deserialize(img.attribute_string) for img in images]

    return data, head, meta