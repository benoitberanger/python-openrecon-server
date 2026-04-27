#!/bin/python3

from utils.ImageFactory import ImageFactory
from utils.check_OR_arguments import check_OR_arguments
from utils.img_array import flatten, get_magnitude, get_subarray
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

def process_image(img_array: npt.NDArray, configJSON: dict | None, metadata) :
    """Invert contrast process image"""
    
    # Create debug folder, if necessary
    if not os.path.exists(debugFolder):
        os.makedirs(debugFolder)
        logging.debug("Created folder " + debugFolder + " for debug output files")

    logging.info(f'-----------------------------------------------')
    logging.info(f'     Echos summation called')
    logging.info(f'-----------------------------------------------')
    
    mem = log_memory("Begining process_image")

    # Get the number of contrasts (dim 1)
    n_contrasts = img_array.shape[1]
    logging.info("Summing %d echoes (contrasts)", n_contrasts)

    # Get the first contrast in magnitude images
    # and use them as reference for head and meta
    ref_images = flatten(get_subarray(img_array, img_contrast=0, img_image_type=ismrmrd.IMTYPE_MAGNITUDE))
    head = [img.getHead()                                  for img in ref_images]
    meta = [ismrmrd.Meta.deserialize(img.attribute_string) for img in ref_images]

    # Stack first contrast : [img, cha, z, y, x]
    data_sum   = np.stack([img.data for img in ref_images]).astype(np.float32)
    del ref_images
    mem = log_memory_delta("After stack contrast 0", mem)

    # Sum the following contrast
    for co in range(1, n_contrasts):
        images_co = flatten(get_subarray(img_array, img_contrast=co, img_image_type=ismrmrd.IMTYPE_MAGNITUDE))
        data_co   = np.stack([img.data for img in images_co]).astype(np.float32)
        data_sum += data_co
        del images_co, data_co
        gc.collect()
        mem = log_memory_delta(f"After adding contrast {co}", mem)

    gc.collect()

    # Normalisation
    BitsStored = 12
    maxVal     = 2**BitsStored - 1
    data_sum  *= maxVal / data_sum.max()
    np.around(data_sum, out=data_sum)
    data_sum   = data_sum.astype(np.int16)
    mem = log_memory_delta("After normalisation", mem)

    # Transpose to [y, x, z, cha, img] expected by MRD3Dto2DImages
    data_sum = data_sum.transpose((3, 4, 2, 1, 0))
    np.save(debugFolder + "/imgMagnitudeSum.npy", data_sum)

    # Update Meta informations of the images
    logging.debug("Update meta here")
    meta = updateMeta(meta, ['PYTHON', 'ECHO_SUM'], 'echosum')
    
    return data_sum, head, meta
