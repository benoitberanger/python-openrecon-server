#!/usr/bin/python3

from server.connection import Connection

import argparse
import datetime
import ismrmrd
import json
import h5py
import logging
import multiprocessing
import os
import socket
import sys
import time

defaults = {
    'filename':           '',
    'in_group':           '',
    'address':            'localhost',
    'port':               9002,
    'outfile':            None,
    'out_group':          str(datetime.datetime.now()),
    'config_json':        'openrecon.json',
    'verbose':            False,
    'logfile':            '',
}


def connection_receive_loop(sock: int, outfile: str, outgroup: str, verbose: bool, logfile: str, recvImages: int):
    """Start a Connection instance to receive data, generally run in a separate thread"""

    if verbose:
        verbosity = logging.DEBUG
    else:
        verbosity = logging.INFO

    if logfile:
        logging.basicConfig(filename=logfile, format='%(asctime)s - %(message)s', level=verbosity)
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
    else:
        logging.basicConfig(format='%(asctime)s - %(message)s', level=verbosity)

    incoming_connection = Connection(sock, True, outfile, "", outgroup)

    try:
        for msg in incoming_connection:
            if msg is None:
                break
    finally:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        sock.close()
        logging.debug("Socket closed (reader)")

        # Dataset may not be closed properly if a close message is not received
        try:
            incoming_connection.dset.close()
        except:
            pass

    recvImages.value    = incoming_connection.recvImages


def load_validate_json(config_json: str) -> str | None:
    if not config_json:
        return None
    if not os.path.exists(config_json):
        logging.info(f"JSON config file not found : {config_json}")
        return None

    logging.info(f"Found JSON config file : {config_json}")
    fid = open(config_json, 'r')
    ConfigJSONText = fid.read()
    fid.close()
    
    return ConfigJSONText


def send_MRD_Metadata(connection: Connection, dset: h5py.Dataset):
    groups = dset.list()
    if ('xml' in groups):
        xml_header = dset.read_xml_header()
        xml_header = xml_header.decode("utf-8")
    else:
        logging.warning("Could not find MRD metadata xml in file")
        xml_header = "Dummy XML header"
    connection.send_metadata(xml_header)
    return xml_header


def send_additional_config(connection: Connection, dset: h5py.Dataset, config_json: str, filename: str) -> None:
    ConfigJSONText = load_validate_json(config_json)

    groups = dset.list()
    if ConfigJSONText:
        if ('configAdditional' in groups):
            logging.warning("configAdditional found in file %s, but is overriden by local file %s!", filename, config_json)

        connection.send_text(ConfigJSONText)
    else:
        if ('configAdditional' in groups):
            configAdditionalText = dset._dataset['configAdditional'][0]
            configAdditionalText = configAdditionalText.decode("utf-8")

            connection.send_text(configAdditionalText)
        else:
            # Do nothing -- no additional config in local .json file or in MRD file
            pass


def send_raw_data(connection: Connection, dset: h5py.Dataset) -> None:
    logging.info("Starting raw data session")
    logging.info("Found %d raw data readouts", dset.number_of_acquisitions())

    for idx in range(dset.number_of_acquisitions()):
        acq = dset.read_acquisition(idx)
        try:
            connection.send_acquisition(acq)
        except:
            logging.error('Failed to send acquisition %d -- aborting!' % idx)
            break


def send_image_data(connection: Connection, dset: h5py.Dataset) -> None:
    logging.info("Starting image data session")
    groups = dset.list()
    for group in [key for key in groups if (key.startswith('image_') or key.startswith('images_'))]:
        logging.info("Reading images from '/" + args.in_group + "/" + group + "'")

        for imgNum in range(0, dset.number_of_images(group)):
            image = dset.read_image(group, imgNum)

            if not isinstance(image.attribute_string, str):
                image.attribute_string = image.attribute_string.decode('utf-8')

            logging.debug("Sending image %d of %d", imgNum, dset.number_of_images(group)-1)
            try:
                connection.send_image(image)
            except:
                logging.error('Failed to send image %d -- aborting!' % imgNum)
                break


def start_client(address, port: int) -> socket.socket:
    # Spawn a thread to connect and handle incoming data
    logging.info("Connecting to MRD server at %s:%d" % (address, port))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    attempt     = 0
    maxAttempts = 5
    success     = False
    while attempt < maxAttempts:
        try:
            sock.connect((address, port))
        except socket.error as error:
            logging.warning("Failed to connect (%d/%d): %s" % (attempt+1, maxAttempts, error))
            time.sleep(1)
            attempt += 1
        else:
            success = True
            attempt = maxAttempts

    if not success:
        sock.close()
        logging.error("... Aborting")
        return

    return sock


def main(args):
    # ----- Load and validate files ---------------------------------------------
    with h5py.File(args.filename, 'r') as dset:
        if not dset:
            logging.error("Not a valid dataset: %s" % args.filename)
            return
        dsetNames = dset.keys()
        logging.info("File %s contains %d groups:", args.filename, len(dset.keys()))
        print(" ", "\n  ".join(dsetNames))

        if not args.in_group:
            if len(dset.keys()) == 1:
                args.in_group = list(dset.keys())[0]
            else:
                logging.error("Input group not specified and multiple groups are present")
                return


        if args.in_group not in dset:
            logging.error("Could not find group %s", args.in_group)
            return

        group = dset.get(args.in_group)

        logging.info("Reading data from group '%s' in file '%s'", args.in_group, args.filename)

        # ----- Determine type of data stored --------------------------------------
        # Raw data is stored as:
        #   /group/config      text of recon config parameters (optional)
        #   /group/xml         text of ISMRMRD flexible data header
        #   /group/data        array of IsmsmrdAcquisition data + header
        #   /group/waveforms   array of waveform (e.g. PMU) data

        # Image data is stored as:
        #   /group/config              text of recon config parameters (optional)
        #   /group/xml                 text of ISMRMRD flexible data header (optional)
        #   /group/image_0/data        array of IsmrmrdImage data
        #   /group/image_0/header      array of ImageHeader
        #   /group/image_0/attributes  text of image MetaAttributes
        hasRaw   = False
        hasImage = False

        if ('data' in group):
            hasRaw = True

        if len([key for key in group.keys() if (key.startswith('image_') or key.startswith('images_'))]) > 0:
            hasImage = True

    if ((hasRaw is False) and (hasImage is False)):
        logging.error("File does not contain properly formatted MRD raw or image data")
        return

    # ----- Open connection to server ------------------------------------------
    sock = start_client(args.address, args.port)
    recvImages    = multiprocessing.Value('i', 0)
    process = multiprocessing.Process(target=connection_receive_loop, args=(sock, args.outfile, args.out_group, args.verbose, args.logfile, recvImages))
    process.daemon = True
    process.start()

    # This connection is only used for outgoing data.  It should not be used for
    # writing to the HDF5 file as multi-threading issues can occur
    connection = Connection(sock, False)

    # --------------- Send config -----------------------------
    logging.info("Sending config name openrecon")
    connection.send_config_file('openrecon')

    # Ensure ismrmrd package has a context manager
    if not (hasattr(ismrmrd.Dataset, '__enter__') and hasattr(ismrmrd.Dataset, '__exit__')):
        raise Exception("Current ismrmrd Python package does not support context manager as required by this code.  Please update to 1.14.1 or newer")

    with ismrmrd.Dataset(args.filename, args.in_group, create_if_needed=False) as dset:
        # --------------- Send MRD metadata -----------------------
        xml_header = send_MRD_Metadata(connection, dset)

        # --------------- Send additional config -----------------------
        send_additional_config(connection, dset, args.config_json, args.ignore_json_config, args.filename)

        # --------------- Send raw data ----------------------
        if hasRaw:
            send_raw_data(connection, dset)

        # --------------- Send image data ----------------------
        if hasImage:
            send_image_data(connection, dset)

    try:
        connection.send_close()
    except:
        logging.error('Failed to send close message!')

    # Wait for incoming data and cleanup
    logging.debug("Waiting for threads to finish")
    process.join()

    sock.close()
    logging.info("Socket closed (writer)")

    # Save a copy of the MRD XML header now that the connection thread is finished with the file
    logging.debug("Writing MRD metadata to file")
    dset = ismrmrd.Dataset(args.outfile, args.out_group)
    dset.write_xml_header(bytes(xml_header, 'utf-8'))
    dset.close()

    logging.info("---------------------- Summary ----------------------")
    logging.info("Sent %5d images        |  Received %5d images",       connection.sentImages,    recvImages.value)
    logging.info("Results written to %s", args.outfile)
    logging.info("Session complete")

    return


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Example client for MRD streaming format',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('filename',                                        help='Input file')
    parser.add_argument('-a', '--address',                                 help='Address (hostname) of MRD server')
    parser.add_argument('-p', '--port',               type=int,            help='Port')
    parser.add_argument('-o', '--outfile',                                 help='Output file')
    parser.add_argument('-g', '--in-group',                                help='Input data group')
    parser.add_argument('-G', '--out-group',                               help='Output group name')
    parser.add_argument('-c', '--config-json',                             help='JSON file with the config')
    parser.add_argument('-v', '--verbose',            action='store_true', help='Verbose mode')
    parser.add_argument('-l', '--logfile',            type=str,            help='Path to log file')

    parser.set_defaults(**defaults)

    args = parser.parse_args()

    if args.logfile:
        print("Logging to file: ", args.logfile)
        logging.basicConfig(filename=args.logfile, format='%(asctime)s - %(message)s', level=logging.WARNING)
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
    else:
        print("No logfile provided")
        logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.WARNING)

    if args.verbose:
        logging.root.setLevel(logging.DEBUG)
    else:
        logging.root.setLevel(logging.INFO)

    if args.outfile is None:
        base, ext = os.path.splitext(args.filename)
        args.outfile = base + '_results' + ext
        logging.info("Output file not specified -- writing results to %s", args.outfile)

    main(args)