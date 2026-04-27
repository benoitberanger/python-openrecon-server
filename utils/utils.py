#!/bin/python3

from server.connection import Connection

import base64
import ismrmrd
import logging
import numpy as np


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


def display_diagnostic(images: list, head: list, meta: list[ismrmrd.Meta]) -> dict:
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

    diagnostic = {
        'matrix': matrix,
        'fov'   : fov,
        'voxelsize' : voxelsize,
        'read_dir'  : read_dir,
        'phase_dir' : phase_dir,
        'slice_dir' : slice_dir
    }

    return diagnostic


def updateMeta(meta: list[ismrmrd.Meta], process_history: list[str] | str, sequence_description: list[str] | str) -> list[ismrmrd.Meta]:
    """Update Metadata infos of the images"""

    # image_processing_history = []
    # if   type(process_history) is str:
    #     image_processing_history.append(process_history)
    # elif type(process_history) is str and len(process_history) > 0:
    #     image_processing_history.append(process_history)
    # else:
    #     TypeError('bad `process_history` type')
    
    if type(sequence_description) is list:
        sequence_description = '_'.join(sequence_description)

    for m in meta:
        tmpMeta = m
        tmpMeta['DataRole']                      = 'Image'
        tmpMeta['ImageProcessingHistory']        = process_history
        tmpMeta['SequenceDescriptionAdditional'] = sequence_description
        m = tmpMeta

    return meta