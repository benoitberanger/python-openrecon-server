import gc
import importlib
import logging

import ismrmrd
import numpy as np

from time import perf_counter
from server.connection import Connection
from utils.utils import check_OR_arguments
from utils.img_array import build_image_array, get_subarray
from utils.memory import log_memory, log_memory_delta
from utils.utils import send_original_images


class Pipeline:
    """
    Loads and runs the application processing module on a group of MRD images.

    Acts as the bridge between the server infrastructure and the application
    code. Loads the processing module once at instantiation, then for each
    image group: builds the structured array, calls process_image(), and
    sends the results back to the client slice by slice.

    Attributes
    ----------
    connection : Connection
        Active MRD connection used to send processed images and logs.
    app_config : str
        Name of the application module to import
        (e.g. 'invert_contrast', 'sum_of_squares').
    app_directory : str
        Python package containing the application module (e.g. 'app').
    module : module or None
        Loaded application module exposing process_image(). None if
        import failed.
    """

    def __init__(self, connection: Connection, app_config: str, app_directory:str) -> None:
        """
        Initialise the pipeline and load the application module.

        Parameters
        ----------
        connection : Connection
            Active MRD connection for sending results and logs.
        app_config : str
            Name of the application module to load.
        app_directory : str
            Python package directory containing the application module.
        """

        self.connection = connection
        self.app_config = app_config
        self.app_directory = app_directory
        self.max_image_series_index = 0
        self.module = None
        self.load_module()


    def load_module(self) -> None:
        """
        Import the application module from app_directory.app_config.

        Called automatically at instantiation. On ImportError, run() 
        will fall back to sending the original images unmodified.
        """
        try:
            self.module = importlib.import_module(self.app_directory + "." + self.app_config)
            logging.info(f"Starting config {self.app_config} in {self.app_directory} directory")
        except ImportError as e:
            logging.error("Failed to load config '%s' with error:\n  %s", self.app_config, e)
            #TO-DO: How to handle failed loading module ? Stop the server, just raise an error
            # or send back original images if asked with just an error message in the logs
            # Maybe trying to load the app before the server received anything to check the argument


    def images_selector(self, img_array: np.ndarray[ismrmrd.Image], configJSON: dict | None) -> np.ndarray[ismrmrd.Image]:
        """
        Select a subarray of ismrmrd.Image based on the option selected by
        the user in the OpenRecon UI and send via JSON.

        Parameters
        ----------
        img_array : np.ndarray
            nD MRD images array as returned by build_image_array().
        configJSON : dict or None
            JSON configuration from the client.
        
        Returns
        -------
        np.ndarray
            Subarray of MRD images corresponding to the request of the.
        """
        select_type     = check_OR_arguments(configJSON, arg_name='ImageType', arg_type=str, arg_default='All')
        select_echo     = check_OR_arguments(configJSON, arg_name='SelectEcho', arg_type=str, arg_default='All')
        select_serie   = check_OR_arguments(configJSON, arg_name='SelectSerie', arg_type=str, arg_default='All')

        if select_type == 'Magnitude':
            type = ismrmrd.IMTYPE_MAGNITUDE
        elif select_type == 'Phase':
            type = ismrmrd.IMTYPE_PHASE
        else :
            type = None
        
        if select_echo == 'FirstEcho':
            echo = 0
        elif select_echo == 'LastEcho':
            echo = - 1
        else :
            echo = None

        if select_serie == 'FirstSerie' :
            serie = 1
        elif select_serie == 'LastSerie' :
            serie = - 1
        else :
            serie = None

        new_array = get_subarray(img_array, img_contrast = echo, img_image_type = type, img_image_series_index = serie)

        return new_array

        
    def run(self, images: list, configJSON: dict | None, metadata) -> None:
        """
        Run the full processing pipeline on a group of MRD images.

        Steps:
          1. Build a structured ndarray from the image list.
          2. Call process_image() from the loaded application module.
          3. Send the processed volume back as individual 2D slices.

        If no module is loaded, the original images are sent back
        unmodified. If SaveOriginal is not set on False in configJSON, 
        a copy of the original images is sent before processing.

        Processing time is measured and logged in milliseconds.

        Parameters
        ----------
        images : list of ismrmrd.Image
            Group of MRD images to process.
        configJSON : dict or None
            JSON configuration from the client. Supports:

            - ``"SaveOriginal"`` (*bool*) : if True, send the original
              images before the processed ones. Default: True.

        metadata : ismrmrd.xsd.ismrmrdHeader or str
            MRD header forwarded to process_image().
        """
        if (len(images) == 0):
            return []
        
        if self.module is None:
            logging.info("No module loaded. Sending back original images.")
            send_original_images(images, self.connection)
            return []
        
        if check_OR_arguments(configJSON, arg_name='SaveOriginal', arg_type=bool, arg_default=True) == True:
            logging.info("Send original images")
            send_original_images(images, self.connection)

        logging.debug("Processing data with %d images of type %s", len(images), images[0].data.dtype)

        mem = log_memory("run Pipeline", "Before build_image_array")
        img_array = build_image_array(images)
        # save the max value of image_serie_index to make sure 
        # the treated images not overlap the original
        for img in images:
            self.max_image_series_index = max(self.max_image_series_index, img.image_series_index)
        del images
        gc.collect()
        mem = log_memory_delta("run Pipeline", "After build_image_array", mem)

        # Image selector from UI
        img_array = self.images_selector(img_array, configJSON)

        # TO-DO: Replace by a decorator
        # Start timer
        tic = perf_counter()
        
        result = self.module.process_image(img_array, configJSON, metadata)
        del img_array

        # Measure processing time
        toc = perf_counter()
        strProcessTime = "Processing time: %.2f ms" % ((toc-tic)*1000.0)
        logging.info(strProcessTime)
        
        log_memory_delta("run Pipeline", "After process_image", mem)

        # Re-slice back into 2D images and send
        for data, head, meta in result:
            self.send_volume_as_2Dslices(data, head, meta)
            del data, head, meta
            gc.collect()

        log_memory_delta("run Pipeline", "After send_volume_as_2Dslices", mem)


    def send_volume_as_2Dslices(self, data: np.ndarray, head: list[ismrmrd.ImageHeader], meta: list[ismrmrd.Meta]) -> None:
        """
        Re-slice back into 2D MRD images from a processed volume
        and send them to the client one by one.

        Iterates over the last axis of data (image index), extracts each
        slice as a contiguous [cha, z, y, x] array, wraps it in an
        ismrmrd.Image, updates the header and meta attributes, and sends
        it immediately over the connection.

        The image_series_index is incremented using the max_image_series_index 
        stored to avoid overlap with the original image series sent 
        by the client.

        Parameters
        ----------
        data : np.ndarray
            Processed image volume, shape [img, cha, z, y, x].
        head : list of ismrmrd.ImageHeader
            Original headers, one per image.
        meta : list of ismrmrd.Meta
            Original Meta objects, one per image.
        """
        # mem = log_memory("send_volume_as_2Dslices", "Before")

        n_imgs = data.shape[0]

        for i in range(n_imgs):
            slice_data = np.ascontiguousarray(data[i])
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
            oldHeader.image_series_index += (self.max_image_series_index + 1)
            img.setHead(oldHeader)

            # Create a copy of the original ISMRMRD Meta attributes and update
            tmpMeta = meta[i]
            tmpMeta['Keep_image_geometry'] = 1

            img.attribute_string = tmpMeta.serialize()
            # logging.debug("Image MetaAttributes: %s", xml.dom.minidom.parseString(metaXml).toprettyxml())
            # logging.debug("Image data has %d elements", imagesOut[iImg].data.size)

            self.connection.send_image(img)
            del img
            # log_memory_delta("send_volume_as_2Dslices", f"After send image: {i}/{n_imgs - 1}", mem)
