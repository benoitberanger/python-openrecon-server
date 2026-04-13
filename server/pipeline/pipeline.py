#!/bin/python3

import base64
import os
import logging
import numpy as np

import ismrmrd

from server.connection import Connection
from utils.ImageFactory import ImageFactory
from utils.check_OR_arguments import check_OR_arguments

class Pipeline:

    def __init__(self, connection: Connection, module) -> None:
        self.connection = connection
        self.preprocessors = []
        self.processor = module
        self.postprocessors = []

    def run(self, images: list, configJSON, metadata) -> list:
        """All the process apply on an image group"""
        if (len(images) == 0):
            return []
        
        if not self.processor:
            logging.info("Module not loaded. Sending back original images.")
            send_original_images(images, self.connection)
            return []
        
        if check_OR_arguments(configJSON, 'sendOriginal', bool, True) == True:
            send_original_images(images, self.connection)

        logging.debug("Processing data with %d images of type %s", len(images), images[0].data.dtype)


        # Extract image data into a numpy array
        # (for 5D images: MRD supposed [img cha z y x])
        data = np.stack([img.data                              for img in images])
        logging.info(f'MRD supposed organization : [img cha z y x]')
        logging.info(f'MRD data shape : {data.shape}')
        head = [img.getHead()                                  for img in images]
        meta = [ismrmrd.Meta.deserialize(img.attribute_string) for img in images]

        #display diagnostic info in the log
        display_diagnostic(images, head, meta)

        imgfactory = ImageFactory(head, meta)
        # self.preprocessors.append(imgfactory.MRD5Dto3D)

        # data_3d = imgfactory.MRD5Dto3D(data)


        for step in self.preprocessors:
            data = step.run(data, configJSON, metadata)
        
        result = self.processor.process_image(data, head, meta, configJSON, metadata)

        for step in self.postprocessors:
            result = step.run(result, configJSON, metadata)

        #######################################################
        #Just changing the image_series_index of the image without any modification for test
        # images_out = []

        # for image in images:
        #     image.image_series_index = 99
        #     images_out.append(image)
        
        # return images_out
        ######################################################

        return result
    

def send_original_images(images: list, connection: Connection) -> None:
    """Return a copy of original images unprocessed if needed"""

    images_copy = []

    for image in images:
        tmpImg = image

        # Ensure Keep_image_geometry is set to not reverse image orientation
        tmpMeta = ismrmrd.Meta.deserialize(tmpImg.attribute_string)
        tmpMeta['Keep_image_geometry'] = 1
        tmpImg.attribute_string = tmpMeta.serialize()

        images_copy.append(tmpImg)
        
    connection.send_image(images_copy)


def display_diagnostic(images: list, head: list, meta: list[ismrmrd.Meta]) -> None:
    """Display diagnostic info about the images in the log"""

    # Optional serialization of ICE MiniHeader
    if 'IceMiniHead' in meta[0]:
        logging.debug("IceMiniHead[0]: %s", base64.b64decode(meta[0]['IceMiniHead']).decode('utf-8'))

    # Diagnostic info
    matrix    = np.array(head[0].matrix_size  [:]) 
    fov       = np.array(head[0].field_of_view[:])
    voxelsize = fov/matrix
    read_dir  = np.array(images[0].read_dir )
    phase_dir = np.array(images[0].phase_dir)
    slice_dir = np.array(images[0].slice_dir)
    logging.info(f'MRD computed maxtrix [x y z] : {matrix   }')
    logging.info(f'MRD computed fov     [x y z] : {fov      }')
    logging.info(f'MRD computed voxel   [x y z] : {voxelsize}')
    logging.info(f'MRD read_dir         [x y z] : {read_dir }')
    logging.info(f'MRD phase_dir        [x y z] : {phase_dir}')
    logging.info(f'MRD slice_dir        [x y z] : {slice_dir}')
