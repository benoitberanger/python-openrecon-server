#!/bin/python3

import logging
import numpy as np

from server.connection import Connection
from utils.ImageFactory import ImageFactory
from utils.check_OR_arguments import check_OR_arguments
from utils.utils import build_image_array, send_original_images

class Pipeline:

    def __init__(self, connection: Connection, module) -> None:
        self.connection = connection
        self.processor = module

    def run(self, images: list, configJSON, metadata) -> list:
        """All the process apply on an image group"""
        if (len(images) == 0):
            return []
        
        if not self.processor:
            logging.info("Module not loaded. Sending back original images.")
            send_original_images(images, self.connection)
            return []
        
        if check_OR_arguments(configJSON, 'SaveOriginal', bool, True) == True:
            send_original_images(images, self.connection)

        logging.debug("Processing data with %d images of type %s", len(images), images[0].data.dtype)

        img_array = build_image_array(images)
        
        result = self.processor.process_image(img_array, configJSON, metadata)

        return result
