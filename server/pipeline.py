#!/bin/python3

from server.connection import Connection
from utils.check_OR_arguments import check_OR_arguments
from utils.img_array import build_image_array
from utils.memory import log_memory, log_memory_delta
from utils.utils import send_original_images

import gc
import importlib
import ismrmrd
import logging
import numpy as np
import numpy.typing as npt
from time import perf_counter


class Pipeline:

    def __init__(self, connection: Connection, app_config: str, app_directory:str) -> None:
        self.connection = connection
        self.app_config = app_config
        self.app_directory = app_directory
        self.module = None
        self.load_module()


    def load_module(self) -> None:
        try:
            self.module = importlib.import_module(self.app_directory + "." + self.app_config)
            logging.info(f"Starting config {self.app_config} in {self.app_directory} directory")
        except ImportError as e:
            logging.error("Failed to load config '%s' with error:\n  %s", self.app_config, e)


    def run(self, images: list, configJSON, metadata) -> None:
        """All the process apply on an image group"""
        if (len(images) == 0):
            return []
        
        if self.module is None:
            logging.info("No module loaded. Sending back original images.")
            send_original_images(images, self.connection)
            return []
        
        if check_OR_arguments(configJSON, 'SaveOriginal', bool, True) == True:
            send_original_images(images, self.connection)

        logging.debug("Processing data with %d images of type %s", len(images), images[0].data.dtype)

        mem = log_memory("Before build_image_array")
        img_array = build_image_array(images)
        del images
        gc.collect()
        mem = log_memory_delta("After build_image_array", mem)

        # Start timer
        tic = perf_counter()
        
        data, head, meta = self.module.process_image(img_array, configJSON, metadata)

        # Measure processing time
        toc = perf_counter()
        strProcessTime = "Processing time: %.2f ms" % ((toc-tic)*1000.0)
        logging.info(strProcessTime)
        
        log_memory_delta("After process_image", mem)

        # Re-slice back into 2D images
        self.MRD3Dto2DImages(data, head, meta)
        del data, head, meta
        gc.collect()
        log_memory_delta("After MRD3Dto2DImages and gc", mem)


    def MRD3Dto2DImages(self, data: npt.NDArray, head: list[ismrmrd.ImageHeader], meta: list[ismrmrd.Meta]) -> None:
        """ Re-slice back 3D array data of the images into 2D images """
        # mem = log_memory("Before MRD3Dto2DImages")

        n_imgs = data.shape[-1]

        for i in range(n_imgs):
            slice_view = data[..., i]
            slice_data = np.ascontiguousarray(slice_view.transpose(3, 2, 0, 1))
            img = ismrmrd.Image.from_array(
                slice_data,
                transpose=False
            )
            del slice_data

            # Create a copy of the original fixed header and update the data_type
            # (we changed it to int16 from all other types)
            oldHeader = head[i]
            oldHeader.data_type = img.data_type

            # Set the image_type to match the data_type for complex data
            if img.data_type in (ismrmrd.DATATYPE_CXFLOAT, ismrmrd.DATATYPE_CXDOUBLE):
                oldHeader.image_type = ismrmrd.IMTYPE_COMPLEX

            # Set the index of the new series image (to not overlap with the original images send)
            oldHeader.image_series_index += 42
            img.setHead(oldHeader)

            # Create a copy of the original ISMRMRD Meta attributes and update
            tmpMeta = meta[i]
            logging.debug(f"Meta update processing history: {tmpMeta['ImageProcessingHistory']}")
            tmpMeta['Keep_image_geometry']           = 1

            img.attribute_string = tmpMeta.serialize()
            # logging.debug("Image MetaAttributes: %s", xml.dom.minidom.parseString(metaXml).toprettyxml())
            # logging.debug("Image data has %d elements", imagesOut[iImg].data.size)

            self.connection.send_image(img)
            del img
            # log_memory_delta(f"After send image: {i}/{n_imgs - 1}", mem)
