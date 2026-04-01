#!/bin/python3

import ismrmrd

from server.connection import Connection

import processing.pre_processing as pre_proc
import processing.post_processing as post_proc

import logging
import importlib

from utils.check_OR_arguments import check_OR_arguments


class Pipeline:
    def __init__(self, connection: Connection, module) -> None:
        self.connection = connection
        self.preprocessors = []
        self.processor = module
        self.postprocessors = []

    def run(self, images, config, metadata):

        if check_OR_arguments(config, 'sendOriginal', bool, True) == True:
            send_original_images(images, self.connection, config, metadata)

        for step in self.preprocessors:
            images = step(images, self.connection, config, metadata)
        
        result = self.processor.process_image(images, config, metadata)

        for step in self.postprocessors:
            result = step.run(result, config, metadata)

        return result
    

def send_original_images(images: list, connection: Connection, config: str, metadata: str) -> None:
    """Return a copy of original images unprocessed if needed"""

    images_copy = []

    for image in images:
        tmpImg = image

        #TO-DO: find a way to handle the image_series_index for the copy
        tmpImg.image_series_index = 99

        # Ensure Keep_image_geometry is set to not reverse image orientation
        tmpMeta = ismrmrd.Meta.deserialize(tmpImg.attribute_string)
        tmpMeta['Keep_image_geometry'] = 1
        tmpImg.attribute_string = tmpMeta.serialize()

        images_copy.append(tmpImg)
        
    connection.send_image(images_copy)
