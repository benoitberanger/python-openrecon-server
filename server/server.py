#!/usr/bin/python3

from utils.check_OR_arguments import check_OR_arguments
from server.debug import send_back_debug
from server.pipeline import Pipeline
from server.connection import Connection
import server.constants as constants

import ismrmrd
import json
import logging
import signal
import socket
import traceback


class Server:
    """Server class"""

    def __init__(self, port: int, address: str, app_config: str, app_directory: str, savedata: bool, debug: bool) -> None:
        logging.info(f"Starting server and listening for data at {address}:{port}")

        self.app_config = app_config
        self.app_directory = app_directory
        self.savedata = savedata
        self.debug = debug
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


    def handle_metadata(self, connection: Connection) :
        """Handle the reception of metadata"""
        metadata_xml = next(connection)

         # Break if no MRD header was received before a close message (e.g. Gadgetron dependency query)
        if ((metadata_xml is None) & (connection.open is False)):
            logging.info("Connection closed without an MRD header received")
            return
        
        logging.info("XML Metadata: %s", metadata_xml)
        try:
            metadata = ismrmrd.xsd.CreateFromDocument(metadata_xml)
            if (metadata.acquisitionSystemInformation.systemFieldStrength_T != None):
                logging.info("Data is from a %s %s at %1.1fT", metadata.acquisitionSystemInformation.systemVendor, metadata.acquisitionSystemInformation.systemModel, metadata.acquisitionSystemInformation.systemFieldStrength_T)
        except:
            logging.warning("Metadata is not a valid MRD XML structure.  Passing on metadata as text")
            metadata = metadata_xml

        return metadata


    def handleJSON(self, connection: Connection, config: str):
        """Handle additional config parameters passed through a JSON text message """
        if connection.peek_mrd_message_identifier() == constants.MRD_MESSAGE_TEXT:
            configAdditionalText = next(connection)
            logging.info(f"Received additional config text: {configAdditionalText}")
            try:
                configAdditional = json.loads(configAdditionalText)
            except Exception as e:
                logging.error("Failed to parse as JSON")
                logging.debug(f"JSON loads error: {e}")
        else:
            configAdditional = config
        
        return configAdditional


    def handle_image_stream(self, connection: Connection, configJSON: dict | None, metadata) -> None:
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

        # Check if the debug mode is enabled via JSON
        if (not self.debug) and check_OR_arguments(configJSON, 'Debug', bool, False) == True :
            self.debug = True
        
        # Initialize the pipeline (only required without the debug mode)
        pipeline = None
        if not self.debug:
            pipeline = Pipeline(connection, self.app_config, self.app_directory)

        # Continuously parse incoming data parsed from MRD messages
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
                    # If the debug mode is activated, send back original images
                    # with image infos displayed in the log
                    if self.debug:
                        send_back_debug(item, connection)
                    else:
                        imgGroup.append(item)

                elif item is None:
                    logging.info("Exit because null item received")
                    break

                else:
                    raise Exception("Unsupported data type %s", type(item).__name__)

            # Process images data.
            if len(imgGroup) > 0:
                logging.info("Processing a group of images")
                images = pipeline.run(imgGroup, configJSON, metadata)
                connection.send_image(images)

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
            # With OpenRecon it supposed to be "openrecon"
            config = next(connection)

            if ((config is None) & (connection.open is False)):
                logging.info("Connection closed without any data received")
                return
            logging.info(f"Received config: {config}")
            
            # Second messages is the metadata (text)
            metadata = self.handle_metadata(connection)
            if not metadata:
                return
            
            # Additional config parameters passed through a JSON text message
            configJSON = self.handleJSON(connection, config)

            # If the config is openrecon load the app config
            # Else do nothing with the data
            if (config == "openrecon"):
                # pipeline = pipeline_factory(connection, self.app_config, self.app_directory)
                self.handle_image_stream(connection, configJSON, metadata)
            else :
                logging.info(f"No openrecon config requested : {config}")
                try:
                    for msg in connection:
                        if (not connection.open) or (msg is None):
                            break
                finally:
                    connection.send_close()

        except Exception as e:
            logging.exception(e)
        
        finally:
            connection.shutdown_close()
