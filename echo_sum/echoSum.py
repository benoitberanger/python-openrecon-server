#!/bin/python3

from utils.ImageFactory import ImageFactory
from utils.check_OR_arguments import check_OR_arguments
from utils.img_array import flatten, get_magnitude_images, get_subarray, stack_images
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
    Combine multi-echo magnitude images into a single image per slice.

    Two combination modes are supported, selected via the 'EchoSumConfig'
    JSON parameter:

    - ``'SimpleSum'`` (default) : direct sum of magnitude echoes
    - ``'SoS'`` : sum of squares followed by a square root

    The result is normalised to 12-bit range and transposed to the
    [y, x, z, cha, img] layout expected by send_volume_as_slices().

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
        Combined image volume, shape [y, x, z, cha, img], dtype int16.
    head : list of ismrmrd.ImageHeader
        Headers from the first contrast, used as reference for output.
    meta : list of ismrmrd.Meta
        Updated Meta objects
    """
    
    # Create debug folder, if necessary
    if not os.path.exists(debugFolder):
        os.makedirs(debugFolder)
        logging.debug("Created folder " + debugFolder + " for debug output files")

    logging.info(f'-----------------------------------------------')
    logging.info(f'     Echos summation called')
    logging.info(f'-----------------------------------------------')
    
    mem = log_memory("Begining process_image")

    # --- OR Parameters ---------------------------------------------------
    sum_config = check_OR_arguments(configJSON, 'EchoSumConfig', str, 'SimpleSum')
    logging.info(f"Echos summation config: {sum_config}")
    
    # --- Dimensions ------------------------------------------------------
    # Get the number of contrasts (img_array axis 1)
    n_contrasts = img_array.shape[1]
    logging.info("Summing %d echoes (contrasts)", n_contrasts)

    # --- Stack first echo (reference for head and meta) ------------------
    # Head and meta are taken from contrast 0, magnitude.
    # Initialise data_sum with the first echo
    # SoS: accumulate squared values, then take sqrt at the end
    # SimpleSum: accumulate raw values directly
    first_echo_images = get_subarray(img_array, img_contrast=0, img_image_type=ismrmrd.IMTYPE_MAGNITUDE)
    data_sum, head, meta = stack_images(first_echo_images) #[img, cha, z, y, x], head, meta
    del first_echo_images
    
    if (sum_config == 'SoS'):
        np.square(data_sum, out=data_sum)
    mem = log_memory_delta("After stacking echo 0", mem)

    # --- Sum with remaining echoes ---------------------------------------
    # SoS: accumulate squared values, then take sqrt at the end
    # SimpleSum: accumulate raw values directly
    for co in range(1, n_contrasts):
        images_co = get_subarray(img_array, img_contrast=co, img_image_type=ismrmrd.IMTYPE_MAGNITUDE)
        data_co, _, _ = stack_images(images_co)
        if (sum_config == 'SoS'):
            np.square(data_co, out=data_co)
        data_sum += data_co
        del images_co, data_co
        gc.collect()
        mem = log_memory_delta(f"After adding echo {co}", mem)

    gc.collect()

    # SoS finalisation: square root of the accumulated squared sum
    if (sum_config == 'SoS'):
        np.sqrt(data_sum, out=data_sum)

    # --- Normalisation to 12-bit range -----------------------------------
    BitsStored = 12
    maxVal     = 2**BitsStored - 1

    data_sum  *= maxVal / data_sum.max()
    np.around(data_sum, out=data_sum)
    data_sum   = data_sum.astype(np.int16)
    mem = log_memory_delta("After normalisation", mem)

    # --- Transpose to [y, x, z, cha, img] --------------------------------
    # send_volume_as_slices() expects this axis order to extract
    # individual 2D slices along the last dimension.
    data_sum = data_sum.transpose((3, 4, 2, 1, 0))
    np.save(debugFolder + "/imgMagnitudeSum.npy", data_sum)
    
    # --- Update metadata -------------------------------------------------
    # TO-DO: Adapat Metadata to the config of sum
    meta = updateMeta(meta, ['PYTHON', 'ECHO_SUM'], 'echosum')
    
    return data_sum, head, meta
