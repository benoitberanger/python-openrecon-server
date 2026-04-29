#!/bin/python3

from utils.ImageFactory import ImageFactory
from utils.check_OR_arguments import check_OR_arguments
from utils.img_array import get_magnitude_images, get_subarray, stack_images
from utils.memory import log_memory, log_memory_delta
from utils.utils import display_diagnostic, updateMeta

import base64
import gc
import ismrmrd
import logging
import numpy as np
import numpy.typing as npt
import os
import xml


# Folder for debug output files
debugFolder = "/tmp/share/debug"

def process_image(img_array: npt.NDArray, configJSON: dict | None, metadata) -> tuple[npt.NDArray, list, list]:
    """
    Invert contrast process image

    Parameters
    ----------
    img_array : np.ndarray
        7D MRD image array [slice, contrast, average, phase,
        repetition, set, image_type] as returned by build_image_array()
    configJSON : dict or None
        JSON configuration from the client
    metadata : ismrmrd.xsd.ismrmrdHeader or str
        MRD header

    Returns
    -------
    data : np.ndarray
        Inverted image volume, shape [y, x, z, cha, img], dtype int16.
    head : list of ismrmrd.ImageHeader
        Original headers from magnitude images.
    meta : list of ismrmrd.Meta
        Updated Meta objects
    """
    
    # Create debug folder, if necessary
    if not os.path.exists(debugFolder):
        os.makedirs(debugFolder)
        logging.debug("Created folder " + debugFolder + " for debug output files")

    logging.info(f'-----------------------------------------------')
    logging.info(f'     invertContrast called')
    logging.info(f'-----------------------------------------------')
    
    mem = log_memory("Begining process_image")

    # --- stack images ----------------------------------------------------
    # sub_images = get_subarray(img_array, img_slice=slice(50,100), img_image_type=ismrmrd.IMTYPE_MAGNITUDE)
    data, head, meta = stack_images(img_array)
    del img_array
    
    # display diagnostic info in the log
    display_diagnostic(head, meta)

    # --- Transpose to [y, x, z, cha, img] --------------------------------
    # send_volume_as_slices() expects this axis order to extract
    # individual 2D slices along the last dimension.
    data = data.transpose((3, 4, 2, 1, 0))

    # --- Normalise to 12-bit range and convert to int16 ------------------
    BitsStored = 12
    maxVal = 2**BitsStored - 1

    data = data.astype(np.float32)
    mem = log_memory_delta("After astype float32", mem)
    data *= maxVal/data.max()
    np.around(data, out=data)
    data = data.astype(np.int16)
    gc.collect()
    mem = log_memory_delta("After astype int16", mem)

    # --- Invert contrast -------------------------------------------------
    data = maxVal-data
    data = np.abs(data)
    np.save(debugFolder + "/" + "imgInverted.npy", data)
    mem = log_memory_delta("After inversion", mem)

    # --- Update metadata -------------------------------------------------
    meta = updateMeta(meta, ['PYTHON', 'INVERT'], 'invertcontrast')

    log_memory_delta("End process_image", mem)
    return data, head, meta
