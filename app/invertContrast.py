#!/bin/python3

import base64
import gc
import logging
import os
import xml

import ismrmrd
import numpy as np

from utils.check_OR_arguments import check_OR_arguments
from utils.img_array import get_magnitude_images, get_subarray, stack_images
from utils.memory import log_memory, log_memory_delta
from utils.utils import display_diagnostic, updateMeta


# Folder for debug output files
debugFolder = "/tmp/share/debug"

def process_image(img_array: np.ndarray[ismrmrd.Image], configJSON: dict | None, metadata) -> tuple[np.ndarray, list, list]:
    """
    Invert contrast process image.

    Parameters
    ----------
    img_array : np.ndarray
        7D MRD image array [slice, contrast, average, phase,
        repetition, set, image_type] as returned by build_image_array().
    configJSON : dict or None
        JSON configuration from the client.
    metadata : ismrmrd.xsd.ismrmrdHeader or str
        MRD header.

    Returns
    -------
    data : np.ndarray
        Inverted image volume, shape [y, x, z, cha, img], dtype int16.
    head : list of ismrmrd.ImageHeader
        Original headers from magnitude images.
    meta : list of ismrmrd.Meta
        Updated Meta objects.
    """
    
    # Create debug folder, if necessary
    if not os.path.exists(debugFolder):
        os.makedirs(debugFolder)
        logging.debug("Created folder " + debugFolder + " for debug output files")

    logging.info(f'------------------------------------------------')
    logging.info(f'     invertContrast called')
    logging.info(f'------------------------------------------------')
    
    mem = log_memory("process_image", "Begining")
    
    # --- Dimensions ------------------------------------------------------
    # Get the number of image_type (img_array axis 6)
    n_image_type = img_array.shape[6]
    image_type_name = ('', 'MAGNITUDE', 'PHASE', 'REAL', 'IMAG', 'COMPLEX', 'RGB')

    # --- Treat all types of images ---------------------------------------
    data_all = []
    head = []
    meta = []

    for image_type in range(1, n_image_type):

        # --- stack images ------------------------------------------------
        sub_array = get_subarray(img_array, img_image_type=image_type)
        tmp_data, tmp_head, tmp_meta = stack_images(sub_array)
        mem = log_memory_delta("process_image", "After stack_images", mem)
        del sub_array
        
        logging.info("  --- Invert contrast on %d %s images ---", len(tmp_head), image_type_name[image_type])
        
        # display diagnostic info in the log
        if image_type == 1:
            display_diagnostic(tmp_head, tmp_meta)

        # # --- Transpose to [y, x, z, cha, img] ----------------------------
        # # send_volume_as_slices() expects this axis order to extract
        # # individual 2D slices along the last dimension.
        # tmp_data = tmp_data.transpose((3, 4, 2, 1, 0))

        # --- Normalise to 12-bit range and convert to int16 --------------
        BitsStored = 12
        maxVal = 2**BitsStored - 1

        tmp_data *= maxVal/tmp_data.max()
        np.around(tmp_data, out=tmp_data)
        tmp_data = tmp_data.astype(np.int16)
        gc.collect()
        mem = log_memory_delta("process_image", "After normalisation", mem)

        # --- Invert contrast ---------------------------------------------
        tmp_data = maxVal-tmp_data
        tmp_data = np.abs(tmp_data)
        np.save(debugFolder + "/" + "imgInverted.npy", tmp_data)
        mem = log_memory_delta("process_image", "After inversion", mem)

        # --- Update metadata ---------------------------------------------
        tmp_meta = updateMeta(tmp_meta, ['PYTHON', 'INVERT'], 'invertcontrast')

        data_all.append(tmp_data)
        head.extend(tmp_head)
        meta.extend(tmp_meta)

        del tmp_data
        gc.collect()

        mem = log_memory_delta("process_image", "After results.append", mem)

    # --- Concatenate -----------------------------------------------------
    data = np.concatenate(data_all, axis= 0)
    del data_all
    gc.collect()

    log_memory_delta("process_image", "End", mem)

    logging.info("--- End of invertContrast ---------------------")
    return data, head, meta
