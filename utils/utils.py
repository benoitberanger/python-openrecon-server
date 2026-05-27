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


def display_diagnostic(head: ismrmrd.ImageHeader, meta: ismrmrd.Meta) -> dict:
    """
    Log geometric and acquisition properties of an image group.

    Extracts key spatial parameters from one image header and
    optionally decodes the Siemens ICE MiniHeader from one Meta
    object if present.

    Parameters
    ----------
    head : list of ismrmrd.ImageHeader
        Image headers.
    meta : list of ismrmrd.Meta
        Deserialised Meta objects.

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
    if 'IceMiniHead' in meta:
        logging.debug("IceMiniHead: %s", base64.b64decode(meta['IceMiniHead']).decode('utf-8'))

    # Diagnostic info
    matrix    = np.array(head.matrix_size  [:]) 
    fov       = np.array(head.field_of_view[:])
    voxelsize = fov/matrix
    read_dir  = np.array(head.read_dir )
    phase_dir = np.array(head.phase_dir)
    slice_dir = np.array(head.slice_dir)
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


def MRD5Dto3D(data_mrd5D: np.array) -> np.array:
    """
    TO-DO: docstring
    """

    # Reformat data to [y x z cha img], i.e. [row col] for the first two dimensions
    data_mrd5D = data_mrd5D.transpose((3, 4, 2, 1, 0))

    logging.debug("Original image data is size %s" % (data_mrd5D.shape,))

    data_5d = data_mrd5D.astype(np.float64)

    # Reformat data from [y x z cha img] to [y x img]
    data_3d = data_5d[:,:,0,0,:]
        
    return data_3d
