#!/bin/python3

import ismrmrd
import logging
import numpy as np
import numpy.typing as npt


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
    img_array = np.full(shape, None, dtype=object)

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
    
    logging.debug(idx)
    return img_array[idx]


def get_magnitude(img_array: npt.NDArray) -> npt.NDArray:
    return get_subarray(img_array, img_image_type=ismrmrd.IMTYPE_MAGNITUDE)


def get_phase(img_array: npt.NDArray) -> npt.NDArray:
    return get_subarray(img_array, img_image_type=ismrmrd.IMTYPE_PHASE)


def get_contrast(img_array: npt.NDArray, contrast: int) -> npt.NDArray:
    return get_subarray(img_array, contrast = contrast)


def flatten(arr: npt.NDArray) -> list[ismrmrd.Image]:
    images = []

    for cell in arr.flat:
        if cell is None:
            continue
        images.extend(cell)

    return images