#!/usr/bin/python3

from server.image_stream_debug import image_stream_debug
from server.image_stream import image_stream
from server.pipeline.pipeline_factory import pipeline_factory
from server.connection import Connection
import server.constants as constants

import logging
import socket
import signal
import json
import ismrmrd

from utils.check_OR_arguments import check_OR_arguments

class Server:
    """Server class"""

    def __init__(self, port: int, address: str, app_config: str, savedata: bool) -> None:
        logging.info(f"Starting the server and listening for data at {address}, {port}")

        self.app_config = app_config
        self.savedata = savedata
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((address, port))


    def serve(self, debug: bool) -> None:
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

            self.handle(sock, debug)


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


    def handle(self, sock: int, debug: bool)-> None:
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

            #If the debug mode is activated, execute the debug mode
            if config == "openrecon" and (debug or check_OR_arguments(configJSON, 'debug', bool, False) == True):
                image_stream_debug(connection, configJSON, metadata)
            # If the config is openrecon load the app config
            # Else do nothing with the data
            elif (config == "openrecon"):
                pipeline = pipeline_factory(connection, self.app_config)
                image_stream(connection, configJSON, metadata, pipeline)
            else :
                logging.info(f"No openrecon config requested : {config}")
                try:
                    for msg in connection:
                        if msg is None:
                            break
                finally:
                    connection.send_close()

        except Exception as e:
            logging.exception(e)
        
        finally:
            connection.shutdown_close()
