import base64
import logging

import ismrmrd
import numpy as np
import numpy.typing as npt

from server.connection import Connection


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

def build_image_array(img_list: list) -> npt.NDArray :
    """Build an array to store the image in an organise way"""
    
    # Found the max value for each dimension
    max_idx = {
        "slice": 0,
        "contrast": 0,
        "average": 0,
        "phase": 0,
        "repetition": 0,
        "set": 0,
        "image_type": 0
    }

    for img in img_list:
        max_idx["slice"]      = max(max_idx["slice"], img.slice)
        max_idx["contrast"]   = max(max_idx["contrast"], img.contrast)
        max_idx["average"]    = max(max_idx["average"], img.average)
        max_idx["phase"]      = max(max_idx["phase"], img.phase)
        max_idx["repetition"] = max(max_idx["repetition"], img.repetition)
        max_idx["set"]        = max(max_idx["set"], img.set)
        max_idx["image_type"] = max(max_idx["image_type"], img.image_type)

    shape = tuple(v + 1 for v in max_idx.values())

    # Initialize an empty array with the right size
    img_array = np.empty(shape, dtype=object)
    img_array.fill(None)

    # Fill the array with the images
    for img in img_list:
        key = (
            img.slice,
            img.contrast,
            img.average,
            img.phase,
            img.repetition,
            img.set,
            img.image_type
        )

        if img_array[key] is None:
            img_array[key] = [img]
        else:
            img_array[key].append(img)

    logging.info(f'array shape : {img_array.shape}')

    return img_array


# TO-DO: - add better error handeling with logs when wrong dimensions asked
#        - make a clear documentation for these function
def get_subarray(img_array: npt.NDArray, 
                 img_slice = None, 
                 img_contrast = None, 
                 img_average = None, 
                 img_phase = None, 
                 img_repetition = None, 
                 img_set = None, 
                 img_image_type = None) -> npt.NDArray:
    """Return a subarray depending of the parameters specified"""

    def to_index(x):
            return slice(None) if x is None else x

    idx = (
        to_index(img_slice),
        to_index(img_contrast),
        to_index(img_average),
        to_index(img_phase),
        to_index(img_repetition),
        to_index(img_set),
        to_index(img_image_type),
    )
    
    logging.info(idx)
    return img_array[idx]


def get_magnitude(img_array: npt.NDArray) -> npt.NDArray:
    return get_subarray(img_array, img_image_type=ismrmrd.IMTYPE_MAGNITUDE)


def get_contrast(img_array: npt.NDArray, contrast: int) -> npt.NDArray:
    return get_subarray(img_array, contrast = contrast)


def flatten(arr: npt.NDArray) -> list[ismrmrd.Image]:
    images = []

    for cell in arr.flat:
        if cell is None:
            continue
        images.extend(cell)

    return images