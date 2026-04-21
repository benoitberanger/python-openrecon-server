#!/bin/python3

import importlib

from server.connection import Connection
from utils.check_OR_arguments import check_OR_arguments
from utils.img_array import build_image_array
from utils.utils import send_original_images

import logging


class Pipeline:

    def __init__(self, connection: Connection, app_config: str, app_directory:str) -> None:
        self.connection = connection
        self.app_config = app_config
        self.app_directory = app_directory
        self.module = None
        self.load_module()


    def load_module(self) -> None:
        try:
            self.module = importlib.import_module(self.app_directory + "." + self.app_config)
            logging.info(f"Starting config {self.app_config} in {self.app_directory} directory")
        except ImportError as e:
            logging.error("Failed to load config '%s' with error:\n  %s", self.app_config, e)


    def run(self, images: list, configJSON, metadata) -> list:
        """All the process apply on an image group"""
        if (len(images) == 0):
            return []
        
        if self.module is None:
            logging.info("No module loaded. Sending back original images.")
            send_original_images(images, self.connection)
            return []
        
        if check_OR_arguments(configJSON, 'SaveOriginal', bool, True) == True:
            send_original_images(images, self.connection)

        logging.debug("Processing data with %d images of type %s", len(images), images[0].data.dtype)

        img_array = build_image_array(images)
        result = self.module.process_image(img_array, configJSON, metadata)

        return result
