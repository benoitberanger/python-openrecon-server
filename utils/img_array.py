#!/bin/python3

import logging

import ismrmrd
import numpy as np


# Dimension names for readable error messages
DIMENSION_NAMES = [
    "slice",
    "contrast",
    "average",
    "phase",
    "repetition",
    "set",
    "image_type",
]

def build_image_array(img_list: list[ismrmrd.Image]) -> np.ndarray[ismrmrd.Image] :
    """
    Build a 7D structured array from a flat list of MRD images.

    Each cell of the array corresponds to a unique combination of loop
    counters and image type. The array axes follow this order:

        [slice, contrast, average, phase, repetition, set, image_type]

    Array size along each axis is ``max_observed_value + 1``, so MRD
    index values can be used directly as array indices without remapping.

    Each non-empty cell contains a list of ismrmrd.Image objects sharing
    that exact combination of loop counters and image type.

    Parameters
    ----------
    img_list : list of ismrmrd.Image
        Flat list of MRD images, typically as received from the client.

    Returns
    -------
    np.ndarray
        7D object array of shape
        (n_slices, n_contrasts, n_averages, n_phases,
         n_repetitions, n_sets, n_image_types).
        Empty cells contain None.
    """
    
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

    # Because ismrmrd.IMTYPE_* values start at 1 (magnitude=1, phase=2,
    # real=3, imag=4, complex=5, rgb=6), index 0 along the image_type
    # axis is always empty. This is intentional, it preserves direct
    # index correspondence with the MRD constants.
    logging.info("7D MRD image array shape :")
    logging.info("  [%-10s %-10s %-10s %-10s %-10s %-6s %-10s]",
             "slice", "contrast", "average", "phase", "repetition", "set", "image_type")
    logging.info("  [%-10d %-10d %-10d %-10d %-10d %-6d %-10d]", *img_array.shape)

    return img_array


def validate_index(value, dim_size: int, dim_name: str) -> None:
    """
    Validate that an index (int or slice) is within bounds for a given dimension.

    Parameters
    ----------
    value : None, int, or slice
        Index to validate. None is always valid (selects the full axis).
    dim_size : int
        Size of the dimension in the array.
    dim_name : str
        Human-readable dimension name used in error messages
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


def get_subarray(img_array: np.ndarray[ismrmrd.Image], 
                 img_slice = None, 
                 img_contrast = None, 
                 img_average = None, 
                 img_phase = None, 
                 img_repetition = None, 
                 img_set = None, 
                 img_image_type = None) -> np.ndarray[ismrmrd.Image]:
    """
    Extract a subarray from a 7D MRD images array by selecting specific indices
    along one or more dimensions.

    Array axis order:
    [slice, contrast, average, phase, repetition, set, image_type]
        
    Any argument left as ``None`` selects all indices along that dimension
    (equivalent to ``:`` in NumPy slice notation).
    
    Parameters
    ----------
    img_array : np.ndarray
        7D MRD images array as returned by build_image_array().
    img_slice : int or None
        Index along the slice axis, or None for all slices.
    img_contrast : int or None
        Index along the contrast axis, or None for all contrasts.
    img_average : int or None
        Index along the average axis, or None for all averages.
    img_phase : int or None
        Index along the phase axis, or None for all phases.
    img_repetition : int or None
        Index along the repetition axis, or None for all repetitions.
    img_set : int or None
        Index along the set axis, or None for all sets.
    img_image_type : int or None
        Index along the image_type axis. Use ismrmrd.IMTYPE_* constants
        directly (e.g. ismrmrd.IMTYPE_MAGNITUDE = 1), or None for all types.

    Returns
    -------
    np.ndarray
        Subarray view corresponding to the requested indices.
    """

    args = [
        img_slice, 
        img_contrast, 
        img_average, 
        img_phase,
        img_repetition, 
        img_set, 
        img_image_type,
    ]

    # Validate every requested index against the actual array shape
    for value, dim_size, dim_name in zip(args, img_array.shape, DIMENSION_NAMES):
        validate_index(value, dim_size, dim_name)
    
    def to_index(x):
        return slice(None) if x is None else x
    
    idx = tuple(to_index(v) for v in args)
    
    # TO-DO: Make this log understandable and clear
    # logging.debug("Extracting subarray with index tuple: %s", idx)
    new_array = img_array[idx]
    logging.info(f"Subarray shape: {new_array.shape}")
    return new_array


def get_magnitude_images(img_array: np.ndarray[ismrmrd.Image]) -> np.ndarray[ismrmrd.Image]:
    """
    Extract the magnitude images from the MRD images array.
    Shorthand for get_subarray(img_array, img_image_type=ismrmrd.IMTYPE_MAGNITUDE).

    Parameters
    ----------
    img_array : np.ndarray
        7D MRD images array as returned by build_image_array().

    Returns
    -------
    np.ndarray
        6D subarray of shape [slice, contrast, average, phase, repetition, set]
        containing only magnitude images.
    """
    return get_subarray(img_array, img_image_type=ismrmrd.IMTYPE_MAGNITUDE)


def get_phase_images(img_array: np.ndarray[ismrmrd.Image]) -> np.ndarray[ismrmrd.Image]:
    """
    Extract the phase images from the MRD images array.
    Shorthand for get_subarray(img_array, img_image_type=ismrmrd.IMTYPE_PHASE).

    Parameters
    ----------
    img_array : np.ndarray
        7D MRD images array as returned by build_image_array().

    Returns
    -------
    np.ndarray
        6D subarray of shape [slice, contrast, average, phase, repetition, set]
        containing only phase images.
    """
    return get_subarray(img_array, img_image_type=ismrmrd.IMTYPE_PHASE)


def get_contrast(img_array: np.ndarray[ismrmrd.Image], contrast: int) -> np.ndarray[ismrmrd.Image]:
    """
    Extract all images for a specific contrast index.
    Shorthand for get_subarray(img_array, img_contrast=contrast).

    Parameters
    ----------
    img_array : np.ndarray
        7D MRD images array as returned by build_image_array().
    contrast : int
        Contrast index to extract (0-based, matches MRD idx.contrast).

    Returns
    -------
    np.ndarray
        6D subarray of shape [slice, average, phase, repetition, set, image_type]
        containing all images for the requested contrast.
    """
    return get_subarray(img_array, contrast = contrast)


def flatten(arr: np.ndarray[ismrmrd.Image]) -> list[ismrmrd.Image]:
    """
    Return a flat list of all MRD images contained in an array or subarray.

    Iterates over every cell of the array in row-major order, skipping
    None cells, and extends the output list with the images found in each
    non-empty cell. Cell order matches NumPy's default flat iteration:
    slice → contrast → average → phase → repetition → set → image_type.

    Parameters
    ----------
    arr : np.ndarray
        Full 7D MRD image array or any subarray returned by get_subarray(),
        get_magnitude(), get_phase_images(), or get_contrast()...

    Returns
    -------
    list of ismrmrd.Image
        All non-None images in the array, in row-major iteration order.
    """
    images = []

    for cell in arr.flat:
        if cell is None:
            continue
        images.extend(cell)

    return images

def stack_images(img_array: np.ndarray[ismrmrd.Image], dtype = np.float32) -> tuple[np.ndarray, list, list]:
    """
    Flatten a MRD image array and stack pixel data, headers and metadata.

    Parameters
    ----------
    img_array : np.ndarray
        7D array or any subarray returned by get_subarray(),
        get_magnitude_images(), get_contrast(), etc.
    dtype : np.dtype, optional
        Output array dtype. Default is np.float32.

    Returns
    -------
    data : np.ndarray
        Stacked pixel data, shape [img, cha, z, y, x], cast to dtype.
    head : list of ismrmrd.ImageHeader
        Headers in the same order as data.
    meta : list of ismrmrd.Meta
        Deserialised Meta objects in the same order as data.

    Raises
    ------
    ValueError
        If img_array contains no images (all cells are None).
    """
    images = flatten(img_array)

    if not images:
        raise ValueError("stack_images: no images found in the provided array.")
    
    logging.debug("Stacking %d images of dtype %s", len(images), images[0].data.dtype)
    
    # MRD supposed organisation [img cha z y x]
    data = np.stack([img.data for img in images]).astype(dtype)
    head = [img.getHead()                                  for img in images]
    meta = [ismrmrd.Meta.deserialize(img.attribute_string) for img in images]

    del images
    logging.debug("Stacked data shape [img, cha, z, y, x]: %s", data.shape)
    
    return data, head, meta
