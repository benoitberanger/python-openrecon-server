#!/bin/python3

from utils.ImageFactory import ImageFactory
from utils.check_OR_arguments import check_OR_arguments
from utils.img_array import flatten, get_magnitude, get_subarray


import base64
import ismrmrd
import logging
import numpy as np
import numpy.typing as npt
import os
import xml


# Folder for debug output files
debugFolder = "/tmp/share/debug"

def process_image(img_array: npt.NDArray, configJSON: dict, metadata) -> list[ismrmrd.Image]:
    """Invert contrast process image"""
    
    # Create debug folder, if necessary
    if not os.path.exists(debugFolder):
        os.makedirs(debugFolder)
        logging.debug("Created folder " + debugFolder + " for debug output files")

    logging.info(f'-----------------------------------------------')
    logging.info(f'     invertContrast called')
    logging.info(f'-----------------------------------------------')
    
    # mag_images = get_subarray(img_array, contrast= 1, img_image_type=ismrmrd.IMTYPE_MAGNITUDE)
    mag_images = get_magnitude(img_array)
    logging.info(f'Magnitude images shape : {mag_images.shape}')
    images = flatten(mag_images)
    logging.debug(f'Number of magnitude images : {len(images)}')

    # Extract image data into a numpy array
    # (for 5D images: MRD supposed [img cha z y x])
    data = np.stack([img.data                              for img in images])
    logging.info(f'MRD supposed organization : [img cha z y x]')
    logging.info(f'MRD data shape : {data.shape}')
    head = [img.getHead()                                  for img in images]
    meta = [ismrmrd.Meta.deserialize(img.attribute_string) for img in images]

    #display diagnostic info in the log
    # diagnostic = display_diagnostic(images, head, meta)

    data = data.transpose((3, 4, 2, 1, 0))

    BitsStored = 12
    maxVal = 2**BitsStored - 1

    # Normalize and convert to int16
    data = data.astype(np.float64)
    data *= maxVal/data.max()
    data = np.around(data)
    data = data.astype(np.int16)

     # Invert image contrast
    data = maxVal-data
    data = np.abs(data)
    np.save(debugFolder + "/" + "imgInverted.npy", data)
    
    # TO-DO: Move that part in a dedicated function
    # Re-slice back into 2D images
    imagesOut = [None] * data.shape[-1]
    for iImg in range(data.shape[-1]):
        # Create new MRD instance for the inverted image
        # Transpose from convenience shape of [y x z cha] to MRD Image shape of [cha z y x]
        # from_array() should be called with 'transpose=False' to avoid warnings, and when called
        # with this option, can take input as: [cha z y x], [z y x], or [y x]
        imagesOut[iImg] = ismrmrd.Image.from_array(data[...,iImg].transpose((3, 2, 0, 1)), transpose=False)

        # Create a copy of the original fixed header and update the data_type
        # (we changed it to int16 from all other types)
        oldHeader = head[iImg]
        oldHeader.data_type = imagesOut[iImg].data_type

        # Set the image_type to match the data_type for complex data
        if (imagesOut[iImg].data_type == ismrmrd.DATATYPE_CXFLOAT) or (imagesOut[iImg].data_type == ismrmrd.DATATYPE_CXDOUBLE):
            oldHeader.image_type = ismrmrd.IMTYPE_COMPLEX

        # Unused example, as images are grouped by series before being passed into this function now
        oldHeader.image_series_index = 99

        imagesOut[iImg].setHead(oldHeader)

        # Create a copy of the original ISMRMRD Meta attributes and update
        tmpMeta = meta[iImg]
        tmpMeta['DataRole']                       = 'Image'
        tmpMeta['ImageProcessingHistory']         = ['PYTHON', 'INVERT']
        tmpMeta['Keep_image_geometry']            = 1

        metaXml = tmpMeta.serialize()
        # logging.debug("Image MetaAttributes: %s", xml.dom.minidom.parseString(metaXml).toprettyxml())
        # logging.debug("Image data has %d elements", imagesOut[iImg].data.size)

        imagesOut[iImg].attribute_string = metaXml

    return imagesOut
