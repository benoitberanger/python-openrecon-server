#!/bin/python3

import base64
import logging

import ismrmrd
import numpy as np

from server.connection import Connection


def send_original_images(images: list[ismrmrd.Image], connection: Connection) -> None:
    """
    Return a copy of original images unprocessed.

    Parameters
    ----------
    images : list of ismrmrd.Image
        List of original MRD Images
    connection : Connection
        Active MRD connection.
    """

    images_copy = []

    for image in images:
        tmpImg = image

        # Ensure Keep_image_geometry is set to not reverse image orientation
        tmpMeta = ismrmrd.Meta.deserialize(tmpImg.attribute_string)
        tmpMeta['Keep_image_geometry'] = 1
        tmpImg.attribute_string = tmpMeta.serialize()

        images_copy.append(tmpImg)
        
    connection.send_image(images_copy)


def display_diagnostic(head: list, meta: list[ismrmrd.Meta]) -> dict:
    """
    Log geometric and acquisition properties of an image group.

    Extracts key spatial parameters from the first image header and
    optionally decodes the Siemens ICE MiniHeader from the first Meta
    object if present.

    Parameters
    ----------
    head : list of ismrmrd.ImageHeader
        Image headers. Only the first element is used, it is assumed
        all images in the group share the same geometry.
    meta : list of ismrmrd.Meta
        Deserialised Meta objects. Only the first element is inspected
        for the optional IceMiniHead field.

    Returns
    -------
    dict with the following keys:

    - ``'matrix'``    — np.ndarray [x, y, z]
    - ``'fov'``       — np.ndarray [x, y, z]
    - ``'voxelsize'`` — np.ndarray [x, y, z]
    - ``'read_dir'``  — np.ndarray [x, y, z]
    - ``'phase_dir'`` — np.ndarray [x, y, z]
    - ``'slice_dir'`` — np.ndarray [x, y, z]
    """

    # Optional serialization of ICE MiniHeader
    if 'IceMiniHead' in meta[0]:
        logging.debug("IceMiniHead[0]: %s", base64.b64decode(meta[0]['IceMiniHead']).decode('utf-8'))

    # Diagnostic info
    matrix    = np.array(head[0].matrix_size  [:]) 
    fov       = np.array(head[0].field_of_view[:])
    voxelsize = fov/matrix
    read_dir  = np.array(head[0].read_dir )
    phase_dir = np.array(head[0].phase_dir)
    slice_dir = np.array(head[0].slice_dir)
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
    """
    Update the ImageProcessingHistory and SequenceDescriptionAdditional
    fields of a list of MRD Meta objects.

    Parameters
    ----------
    meta : list of ismrmrd.Meta
        Meta objects to update, one per image
    process_history : list of str or str
        Processing steps to record (e.g. ['PYTHON', 'INVERT'] or 'INVERT')
    sequence_description : list of str or str
        Sequence label appended to the series name in the client UI.
        (e.g. ['echo', 'sum'] → 'echo_sum', or 'invertcontrast')

    Returns
    -------
    list of ismrmrd.Meta
        The same list, with each Meta updated.
    """
    if isinstance(process_history, str):
        process_history = [process_history]
    
    if isinstance(sequence_description, list):
        sequence_description = '_'.join(sequence_description)

    for m in meta:
        m['DataRole']                      = 'Image'
        m['ImageProcessingHistory']        = process_history
        m['SequenceDescriptionAdditional'] = sequence_description

    return meta    
