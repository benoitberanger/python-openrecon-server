#!/bin/python3

import ismrmrd
import logging
import numpy as np
import numpy.typing as npt

# Dimension names for readable error messages
DIMENSION_NAMES = [
    "img_slice",
    "img_contrast",
    "img_average",
    "img_phase",
    "img_repetition",
    "img_set",
    "img_image_type",
]

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

    # TO-DO: Clear logs about the images array shape to know what is what
    # Since the image_type have a value between 1 and 6, the subarray (:, :, :, :, :, :, 0)
    # will always be empty because for clarity this value is directly use as key 
    logging.info('MRD images array dimension: {slice, average, phase, repetition, set, image_type}')
    logging.info(f'MRD images array shape : {img_array.shape}')

    return img_array


def validate_index(value, dim_size: int, dim_name: str) -> None:
    """
    Validate that an index (int or slice) is within bounds for a given dimension.

    Args:
        value:    None, an integer index, or a slice object.
        dim_size: The size of the dimension in the array.
        dim_name: Human-readable name of the dimension (used in error messages).
    """
    if value is None:
        return

    if isinstance(value, int):
        if not (-dim_size <= value and value < dim_size):
            logging.error(
                "Index out of range for dimension '%s': requested index %d, but dimension size is %d (valid range: [%d, %d]).",
                dim_name, value, dim_size, -dim_size, dim_size - 1
            )
            return

    elif isinstance(value, slice):
        start, stop, step = value.indices(dim_size)
        indices = range(start, stop, step)
        if len(indices) == 0:
            logging.error(
                "Slice out of range for dimension '%s': slice(%s, %s, %s) selects 0 elements from a dimension of size %d.",
                dim_name, value.start, value.stop, value.step, dim_size
            )
            return


def get_subarray(img_array: npt.NDArray, 
                 img_slice = None, 
                 img_contrast = None, 
                 img_average = None, 
                 img_phase = None, 
                 img_repetition = None, 
                 img_set = None, 
                 img_image_type = None) -> npt.NDArray:
    """
    Extract a subarray from a 7-D MRD image array by selecting specific indices
    along one or more dimensions.

    The array axes are expected to follow this order:
    slice, contrast, average, phase, repetition, set, image_type
        
    Any argument left as ``None`` selects all indices along that dimension
    (equivalent to ``:`` in NumPy slice notation).

    Args:
        img_array:      7-D NumPy array containing the MRD data.
        img_slice:      Index along the slice dimension, or None for all.
        img_contrast:   Index along the contrast dimension, or None for all.
        img_average:    Index along the average dimension, or None for all.
        img_phase:      Index along the phase dimension, or None for all.
        img_repetition: Index along the repetition dimension, or None for all.
        img_set:        Index along the set dimension, or None for all.
        img_image_type: Index along the image-type dimension, or None for all.

    Returns:
        A NumPy subarray corresponding to the requested indices.
    """

    args = [
        img_slice, img_contrast, img_average, img_phase,
        img_repetition, img_set, img_image_type,
    ]

    # Validate every requested index against the actual array shape
    for value, dim_size, dim_name in zip(args, img_array.shape, DIMENSION_NAMES):
        validate_index(value, dim_size, dim_name)
    
    def to_index(x):
        return slice(None) if x is None else x
    
    idx = tuple(to_index(v) for v in args)
    
    logging.debug("Extracting subarray with index tuple: %s", idx)
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