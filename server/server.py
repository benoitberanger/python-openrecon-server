#!/usr/bin/python3

from server.connection import Connection
import server.constants as constants

import logging
import socket
import signal
import json
import importlib
import ismrmrd
import traceback

class Server:
    """Server class"""

    def __init__(self, port: int, address: str, config: str, savedata: bool) -> None:
        logging.info(f"Starting the server and listening for data at {address}, {port}")

        self.config = config
        self.savedata = savedata
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((address, port))


    def serve(self) -> None:
        """Serve the server"""

        logging.debug("Serving... ")
        self.socket.listen(0)

        while True:
            try:
                signal.siginterrupt(signal.SIGTERM, True)
                signal.siginterrupt(signal.SIGINT, True)
            except AttributeError:
                # signal.siginterrupt is not available in Windows
                pass

            sock, (remote_addr, remote_port) = self.socket.accept()

            logging.info(f"Accepting connection from: {remote_addr}:{remote_port}")

            self.handle(sock)


    def handle_metadata(self, connection: Connection) -> str | None:
        """Handle the reception of metadata"""
        metadata_xml = next(connection)

         # Break if no MRD header was received before a close message (e.g. Gadgetron dependency query)
        if ((metadata_xml is None) & (connection.open is False)):
            logging.info("Connection closed without an MRD header received")
            return
        
        logging.debug("XML Metadata: %s", metadata_xml)
        try:
            metadata = ismrmrd.xsd.CreateFromDocument(metadata_xml)
            if (metadata.acquisitionSystemInformation.systemFieldStrength_T != None):
                logging.info("Data is from a %s %s at %1.1fT", metadata.acquisitionSystemInformation.systemVendor, metadata.acquisitionSystemInformation.systemModel, metadata.acquisitionSystemInformation.systemFieldStrength_T)
        except:
            logging.warning("Metadata is not a valid MRD XML structure.  Passing on metadata as text")
            metadata = metadata_xml

        return metadata


    def handleJSON(self, connection: Connection, config: str) -> str:
        """Handle additional config parameters passed through a JSON text message """
        if connection.peek_mrd_message_identifier() == constants.MRD_MESSAGE_TEXT:
            configAdditionalText = next(connection)
            logging.info("Received additional config text: %s", configAdditionalText)
            connection.save_additional_config(configAdditionalText)
            try:
                configAdditional = json.loads(configAdditionalText)

                if ('parameters' in configAdditional):
                    if ('config' in configAdditional['parameters']):
                        logging.info("Changing config to: %s", configAdditional['parameters']['config'])
                        config = configAdditional['parameters']['config']

                    if ('customconfig' in configAdditional['parameters']) and (configAdditional['parameters']['customconfig'] != ""):
                        logging.info("Changing config to: %s", configAdditional['parameters']['customconfig'])
                        config = configAdditional['parameters']['customconfig']
            except:
                logging.error("Failed to parse as JSON")
        else:
            configAdditional = config
        
        return configAdditional
            

    def process(self, connection: Connection, config: str, metadata:str) -> None:
        """
        Decide what program to use based on config
        If not one of these explicit cases, try to load file matching name of config
        """
        #########################################################
        #TO-DO: Moved the import
        try:
            module = importlib.import_module("app."+self.config)
            logging.info(f"Starting config {self.config}")
        except ImportError as e:
                    logging.error("Failed to load config '%s' with error:\n  %s", self.config, e)
        #########################################################

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
                if isinstance(item, ismrmrd.Image):
                    connection.send_image(item)
                else :
                    print(f"type: {item.__class__}")
            #     # ----------------------------------------------------------
            #     # Raw k-space data messages
            #     # ----------------------------------------------------------
            #     if isinstance(item, ismrmrd.Acquisition):
            #         raise Exception("Raw k-space data is not supported by this module")

            #     # ----------------------------------------------------------
            #     # Image data messages
            #     # ----------------------------------------------------------
            #     elif isinstance(item, ismrmrd.Image):
            #         # When this criteria is met, run process_group() on the accumulated
            #         # data, which returns images that are sent back to the client.
            #         # e.g. when the series number changes:
            #         if item.image_series_index != currentSeries:
            #             logging.info("Processing a group of images because series index changed to %d", item.image_series_index)
            #             currentSeries = item.image_series_index
            #             image = module.process_image(imgGroup, connection, config, metadata)
            #             connection.send_image(image)
            #             imgGroup = []

            #         # Only process magnitude images -- send phase images back without modification (fallback for images with unknown type)
            #         if (item.image_type is ismrmrd.IMTYPE_MAGNITUDE) or (item.image_type == 0):
            #             imgGroup.append(item)
            #         else:
            #             tmpMeta = ismrmrd.Meta.deserialize(item.attribute_string)
            #             tmpMeta['Keep_image_geometry']    = 1
            #             item.attribute_string = tmpMeta.serialize()

            #             connection.send_image(item)
            #             continue

            #     elif item is None:
            #         break

            #     else:
            #         raise Exception("Unsupported data type %s", type(item).__name__)

            # Process any remaining groups of image data.  This can 
            # happen if the trigger condition for these groups are not met.
            # This is also a fallback for handling image data, as the last
            # image in a series is typically not separately flagged.
            # if len(imgGroup) > 0:
            #     logging.info("Processing a group of images (untriggered)")
            #     image = module.process_image(imgGroup, connection, config, metadata)
            #     connection.send_image(image)
            #     imgGroup = []

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


    def handle(self, sock: int)-> None:
        """Handle each connection on the server socket"""

        try:
            connection = Connection(sock, self.savedata)

            # First message is the config (file or text)
            config = next(connection)

            if ((config is None) & (connection.open is False)):
                logging.info("Connection closed without any data received")
                return
            
            # Second messages is the metadata (text)
            metadata = self.handle_metadata(connection)

            if not metadata:
                return
            
            # Additional config parameters passed through a JSON text message
            configAdditional = self.handleJSON(connection, config)

            # If the config is openrecon load the app config
            # Else do nothing with the data
            if (config == "openrecon"):
                self.process(connection, configAdditional, metadata)
            else :
                logging.info("No openrecon config requested")
                try:
                    for msg in connection:
                        if msg is None:
                            break
                finally:
                    connection.send_close()

        except Exception as e:
            logging.exception(e)
