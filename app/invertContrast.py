#!/bin/python3

from utils.ImageFactory import ImageFactory
from utils.check_OR_arguments import check_OR_arguments
from utils.img_array import flatten, get_magnitude, get_subarray
from utils.memory import log_memory, log_memory_delta
from utils.utils import display_diagnostic

import base64
import gc
import ismrmrd
import logging
import numpy as np
import numpy.typing as npt
import os
from time import perf_counter
import xml


# Folder for debug output files
debugFolder = "/tmp/share/debug"

def process_image(img_array: npt.NDArray[ismrmrd.Images], configJSON: dict, metadata) :
    """Invert contrast process image"""
    
    # Create debug folder, if necessary
    if not os.path.exists(debugFolder):
        os.makedirs(debugFolder)
        logging.debug("Created folder " + debugFolder + " for debug output files")

    logging.info(f'-----------------------------------------------')
    logging.info(f'     invertContrast called')
    logging.info(f'-----------------------------------------------')
    
    mem = log_memory("Begining process_image")

    # Start timer
    tic = perf_counter()
    
    # mag_images = get_subarray(img_array, img_slice= slice(100,250), img_image_type=ismrmrd.IMTYPE_MAGNITUDE)
    mag_images = get_magnitude(img_array)
    logging.info(f'Magnitude images shape : {mag_images.shape}')
    images = flatten(mag_images)
    logging.debug(f'Number of magnitude images : {len(images)}')
    mem = log_memory_delta("After flatten", mem)

    # TO-DO: move that part in a dedicated function in utils
    # Extract image data into a numpy array
    # (for 5D images: MRD supposed [img cha z y x])
    data = np.stack([img.data                              for img in images])
    logging.info(f'MRD supposed organization : [img cha z y x]')
    logging.info(f'MRD data shape : {data.shape}')
    mem = log_memory_delta("After np.stack", mem)

    head = [img.getHead()                                  for img in images]
    meta = [ismrmrd.Meta.deserialize(img.attribute_string) for img in images]
    
    # display diagnostic info in the log
    display_diagnostic(images, head, meta)
    del images

    data = data.transpose((3, 4, 2, 1, 0))

    BitsStored = 12
    maxVal = 2**BitsStored - 1

    # Normalize and convert to int16
    data = data.astype(np.float32)
    mem = log_memory_delta("After astype float64", mem)
    data *= maxVal/data.max()
    np.around(data, out=data)
    data = data.astype(np.int16)
    gc.collect()
    mem = log_memory_delta("After astype int16", mem)

     # Invert image contrast
    data = maxVal-data
    data = np.abs(data)
    np.save(debugFolder + "/" + "imgInverted.npy", data)
    mem = log_memory_delta("After inversion", mem)

    # Measure processing time
    toc = perf_counter()
    strProcessTime = "Processing time: %.2f ms" % ((toc-tic)*1000.0)
    logging.info(strProcessTime)

    return data, head, meta
