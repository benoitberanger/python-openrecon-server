#!/bin/python3

import logging
import traceback

import ismrmrd

from server.connection import Connection
from server.pipeline.pipeline import Pipeline


def image_stream(connection: Connection, configJSON, metadata, pipeline: Pipeline) -> None:
        """
        Treat the images send by the server, send back the result
        """

        # Metadata should be MRD formatted header, but may be a string
        # if it failed conversion earlier
        try:
            logging.info("Incoming dataset contains %d encodings", len(metadata.encoding))
            logging.info("First encoding is of type '%s', with a matrix size of (%s x %s x %s) and a field of view of (%s x %s x %s)mm^3", 
                metadata.encoding[0].trajectory, 
                metadata.encoding[0].encodedSpace.matrixSize.x, 
                metadata.encoding[0].encodedSpace.matrixSize.y, 
                metadata.encoding[0].encodedSpace.matrixSize.z, 
                metadata.encoding[0].encodedSpace.fieldOfView_mm.x, 
                metadata.encoding[0].encodedSpace.fieldOfView_mm.y, 
                metadata.encoding[0].encodedSpace.fieldOfView_mm.z)

        except:
            logging.info("Improperly formatted metadata: \n%s", metadata)

        # Continuously parse incoming data parsed from MRD messages
        currentSeries = 0
        imgGroup = []
        try:
            for item in connection:

                # When the connection is closed, all images have been received
                if not connection.open :
                    logging.info("Exit because connection closed. All images have been received")
                    break

                # ----------------------------------------------------------
                # Raw k-space data messages
                # ----------------------------------------------------------
                if isinstance(item, ismrmrd.Acquisition):
                    logging.error("Raw k-space data is not supported by this module")
                    raise Exception("Raw k-space data is not supported by this module")

                # ----------------------------------------------------------
                # Image data messages
                # ----------------------------------------------------------
                elif isinstance(item, ismrmrd.Image):
                    
                    # When this criteria is met, run process_group() on the accumulated
                    # data, which returns images that are sent back to the client.
                    # e.g. when the series number changes:
                    if item.image_series_index != currentSeries:
                        logging.info("Processing a group of images because series index changed to %d", item.image_series_index)
                        currentSeries = item.image_series_index
                        image = pipeline.run(imgGroup, configJSON, metadata)
                        connection.send_image(image)
                        imgGroup = []

                    # Only process magnitude images -- send phase images back without modification (fallback for images with unknown type)
                    if (item.image_type is ismrmrd.IMTYPE_MAGNITUDE) or (item.image_type == 0):
                        imgGroup.append(item)
                    else:
                        tmpMeta = ismrmrd.Meta.deserialize(item.attribute_string)
                        tmpMeta['Keep_image_geometry']    = 1
                        item.attribute_string = tmpMeta.serialize()

                        connection.send_image(item)
                        continue

                elif item is None:
                    logging.info("Exit because null item received")
                    break

                else:
                    raise Exception("Unsupported data type %s", type(item).__name__)

            # Process any remaining groups of image data.  This can 
            # happen if the trigger condition for these groups are not met.
            # This is also a fallback for handling image data, as the last
            # image in a series is typically not separately flagged.
            if len(imgGroup) > 0:
                logging.info("Processing a group of images (untriggered)")
                images = pipeline.run(imgGroup, configJSON, metadata)
                connection.send_image(images)
                imgGroup = []

        except Exception as e:
            logging.error(traceback.format_exc())
            connection.send_logging("ERROR", traceback.format_exc())
            
            # Close connection without sending MRD_MESSAGE_CLOSE message to signal failure
            connection.shutdown_close()

        finally:
            try:
                connection.send_close()
            except:
                logging.error("Failed to send close message!")
