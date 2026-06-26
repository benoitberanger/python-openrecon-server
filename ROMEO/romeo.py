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
from utils.OutputSeries import OutputSeries, ProcessImageResult
from utils.check_OR_arguments import check_OR_arguments
from utils.img_array import get_type_magnitude, get_subarray, mrd_indexes, stack_images
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
            data, head, meta = stack_images(mag_array)
            tmp_echo = [float(m.get("EchoTime")) for m in meta]
            echo_times = np.unique(tmp_echo).tolist()
            mem = log_memory_delta("process_image", "After stack_images", mem)
            del mag_array

        # get Phase image
        phase_array = get_subarray(img_array, img_image_type=ismrmrd.IMTYPE_PHASE, img_image_series_index=serie_index)
        if phase_array.any():
            nifti_P = nifti_from_image_array(phase_array, "/tmp/share/romeo", ["contrast"])
            # --- stack images ------------------------------------------------
            data, head, meta = stack_images(phase_array)
            tmp_echo = [float(m.get("EchoTime")) for m in meta]
            echo_times = np.unique(tmp_echo).tolist()
            mem = log_memory_delta("process_image", "After stack_images", mem)
            del phase_array

    if not nifti_P:
        logging.error("Phase images not found. Stoping process.")
        return []
    
    logging.info(f"TE = {echo_times}")
    run_ROMEO(nifti_P, nifti_M, echo_times)
    # TO-DO: Convert back the result into (data, head, meta) to send back

        # # display diagnostic info in the log
        # if series is None:
        #     display_diagnostic(head[0], meta[0])
            
        # # --- Normalise to 12-bit range and convert to int16 --------------
        # data = normalise(data)
        # data = data.astype(np.int16)
        # gc.collect()
        # mem = log_memory_delta("process_image", "After normalisation", mem)

        # # --- Add series --------------------------------------------------
        # series.add(data, head, meta, 
        #     process_history = ["PYTHON", "ROMEO Unwrapping"], 
        #     sequence_description = "ROMEOUnwrapping")
        # del data
        # gc.collect()
        # mem = log_memory_delta("process_image", "After series.add", mem)

    if series is None:
        logging.error("No images found in img_array. Returning empty result.")
        return []
    
    log_memory_delta("process_image", "End", mem)
    logging.info("--- End of ROMEO ---------------------")
    return series.get()


def run_ROMEO(nifti_path_P: str, nifti_path_M: str = None, echo_times: list = None):

    cmd = ["julia", "/opt/romeo/romeo.jl", "-o", niftiFolder, "-p", nifti_path_P]
    if nifti_path_M is not None:
        cmd += ["-m", str(nifti_path_M)]
    if echo_times and (len(echo_times) > 1):
        cmd += ["-t", str(echo_times)]

    logging.info(f"running ROMEO unwrapping algorithm : {cmd}")
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    # output default is "unwrapped.nii"
    
