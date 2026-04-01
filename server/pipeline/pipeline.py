#!/bin/python3

import base64
import os
import logging
import importlib

import ismrmrd
import numpy as np

from server.connection import Connection

import processing.pre_processing as pre_process
import processing.post_processing as post_process



from utils.ImageFactory import ImageFactory
from utils.check_OR_arguments import check_OR_arguments

# Folder for debug output files
debugFolder = "/tmp/share/debug"

class Pipeline:
    def __init__(self, connection: Connection, module) -> None:
        self.connection = connection
        self.preprocessors = []
        self.processor = module
        self.postprocessors = []

        # Create debug folder, if necessary
        if not os.path.exists(debugFolder):
            os.makedirs(debugFolder)
            logging.debug("Created folder " + debugFolder + " for debug output files")

    def run(self, images, config, metadata):

        if (len(images) == 0):
            return []
        
        if check_OR_arguments(config, 'sendOriginal', bool, True) == True:
            send_original_images(images, self.connection, config, metadata)

        logging.debug("Processing data with %d images of type %s", len(images), images[0].data.dtype)

###########################################################################
        #TO-DO: refactor into preprocess
        #   (- sort the data by image type ? doing it before ?)
        #   - check_OR_arguments(config, 'InvertContrast', bool, True)
        #   - conversion to numpy array
        #   - diagnostic of data

        # Extract image data into a 5D array of size [img cha z y x]
        data = np.stack([img.data                              for img in images])
        logging.info(f'MRD supposed organization : [img cha z y x]')
        logging.info(f'MRD data shape : {data.shape}')
        head = [img.getHead()                                  for img in images]
        meta = [ismrmrd.Meta.deserialize(img.attribute_string) for img in images]

        #display diagnostic info in the log
        display_diagnostic(images, head, meta)

        imgfactory = ImageFactory(head, meta)

        data_3d = imgfactory.MRD5Dto3D(data)

###########################################################################

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

        # Ensure Keep_image_geometry is set to not reverse image orientation
        tmpMeta = ismrmrd.Meta.deserialize(tmpImg.attribute_string)
        tmpMeta['Keep_image_geometry'] = 1
        tmpImg.attribute_string = tmpMeta.serialize()

        images_copy.append(tmpImg)
        
    connection.send_image(images_copy)


def display_diagnostic(images: list, head: list, meta: list[ismrmrd.Meta]) -> None:
    """Display diagnostic info about the images in the log"""

    # Display MetaAttributes for first image
    logging.debug("MetaAttributes[0]: %s", ismrmrd.Meta.serialize(meta[0]))

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
