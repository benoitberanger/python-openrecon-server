#!/bin/python3

from server.connection import Connection
from utils.ImageFactory import ImageFactory
from utils.check_OR_arguments import check_OR_arguments

import ismrmrd
import numpy as np
import logging
import os
import base64


# Folder for debug output files
debugFolder = "/tmp/share/debug"


def diagnostic_info(images: list, data: np.array, head: list, meta: list[ismrmrd.Meta]) -> None:
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


def process_image(images: list, connection: Connection, config: str, metadata: str):
    """Invert contrast process image"""

    if (len(images) == 0):
        return []
    
    logging.info(f'-----------------------------------------------')
    logging.info(f'     invertContrast called with {len(images)} images')
    logging.info(f'-----------------------------------------------')

    # Create folder, if necessary
    if not os.path.exists(debugFolder):
        os.makedirs(debugFolder)
        logging.debug("Created folder " + debugFolder + " for debug output files")
    
    logging.debug("Processing data with %d images of type %s", len(images), images[0].data.dtype)

    #TO-DO:
    #   - check_OR_arguments(config, 'InvertContrast', bool, True)
    #   - conversion to numpy array
    #   - diagnostic of data

    images_out = images

    return images_out