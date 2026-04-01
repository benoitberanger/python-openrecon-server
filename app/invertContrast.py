#!/bin/python3

from utils.ImageFactory import ImageFactory
from utils.check_OR_arguments import check_OR_arguments

import ismrmrd
import numpy as np
import logging
import os
import base64


# Folder for debug output files
debugFolder = "/tmp/share/debug"


def process_image(images: np.array, config: str, metadata: str):
    """Invert contrast process image"""

    if (len(images) == 0):
        return []
    
    logging.info(f'-----------------------------------------------')
    logging.info(f'     invertContrast called with {len(images)} images')
    logging.info(f'-----------------------------------------------')
    
    #Just changing the image_series_index of the image without any modification for test
    images_out = []

    for image in images:
        image.image_series_index = 99
        images_out.append(image)

    return images_out