#!/bin/python3

import logging
import traceback

import ismrmrd

from server.connection import Connection
from server.pipeline.pipeline import Pipeline


def image_stream_debug(connection: Connection, configJSON, metadata) -> None:
        """
        Treat the images send by the server, send back the result
        """

        logging.info("------------DEBUG MODE------------")

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

        try:
            for item in connection:
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
                    
                    display_info_images(item)

                    tmpMeta = ismrmrd.Meta.deserialize(item.attribute_string)
                    tmpMeta['Keep_image_geometry'] = 1
                    item.attribute_string = tmpMeta.serialize()

                    connection.send_image(item)

                elif item is None:
                    break

                else:
                    raise Exception("Unsupported data type %s", type(item).__name__)

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


def display_info_images(image) -> None:
    """Display in the log info about images info"""

    logging.info('-------------------------------------')
    logging.info('-------------IMAGE INFO--------------')
    logging.info('-------------------------------------')

    image_type = ['0', 'MRD_IMTYPE_MAGNITUDE', 'MRD_IMTYPE_PHASE', 'MRD_IMTYPE_REAL', 'MRD_IMTYPE_IMAG', 'MRD_IMTYPE_COMPLEX', 'MRD_IMTYPE_RGB']
    # logging.info(f'version                  : {image.version}')
    # logging.info(f'data_type                : {image.data_type}')
    logging.info(f'flags                    : {image.flags}')
    # logging.info(f'measurement_uid          : {image.measurement_uid}')
    # logging.info(f'matrix_size              : {image.matrix_size}')
    # logging.info(f'field_of_view            : {image.field_of_view}')
    # logging.info(f'channels                 : {image.channels}')
    # logging.info(f'position                 : {image.position}')
    # logging.info(f'read_dir                 : {image.read_dir}')
    # logging.info(f'phase_dir                : {image.phase_dir}')
    # logging.info(f'slice_dir                : {image.slice_dir}')
    # logging.info(f'patient_table_position   : {image.patient_table_position}')
    logging.info(f'average                  : {image.average}')
    logging.info(f'slice                    : {image.slice}')
    logging.info(f'contrast                 : {image.contrast}')
    logging.info(f'phase                    : {image.phase}')
    logging.info(f'repetition               : {image.repetition}')
    logging.info(f'set                      : {image.set}')
    # logging.info(f'aquisition_time_stamp    : {image.aquisition_time_stamp}')
    # logging.info(f'physiology_time_stamp    : {image.physiology_time_stamp}')
    logging.info(f'image_type               : {image_type[image.image_type]}')
    logging.info(f'image_index              : {image.image_index}')
    logging.info(f'image_series_index       : {image.image_series_index}')
    # logging.info(f'user_int                 : {image.user_int}')
    # logging.info(f'user_float               : {image.user_float}')
    # logging.info(f'attribute_string_len     : {image.attribute_string_len}')
