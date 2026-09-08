import argparse
import datetime
import logging
import multiprocessing
import os
import sys

import ismrmrd

import python_openrecon_server.server.client as client
from python_openrecon_server.server.connection import Connection

defaults = {
    'filename':           '',
    'in_group':           '',
    'address':            'localhost',
    'port':               9002,
    'outfile':            None,
    'out_group':          str(datetime.datetime.now()),
    'config_json':        None,
    'send_waveforms':     False,
    'verbose':            False,
    'logfile':            '',
}


def main(args):

    # --- Output file ---------------------------------------------------------
    if args.outfile is None:
        base, ext = os.path.splitext(args.filename)
        args.outfile = base + '_results' + ext
        logging.info("Output file not specified -- writing results to %s", args.outfile)

    # ----- Validate dataset --------------------------------------------------
    info = client.inspect_dataset(args.filename, args.in_group)

    # ----- Open connection to server -----------------------------------------
    sock = client.connect_to_server(args.address, args.port)
    recvImages = multiprocessing.Value('i', 0)

    process = multiprocessing.Process(
        target = client.connection_receive_loop, 
        args = (sock, args.outfile, args.out_group, args.verbose, args.logfile, recvImages),
        daemon = True)
    process.start()

    # This connection is only used for outgoing data.  It should not be used for
    # writing to the HDF5 file as multi-threading issues can occur
    connection = Connection(sock, False)

    # --- Check ismrmrd context manager support -------------------------------
    if not (hasattr(ismrmrd.Dataset, '__enter__') and hasattr(ismrmrd.Dataset, '__exit__')):
        raise Exception(
            "Current ismrmrd Python package does not support context manager as required by this code. " 
            "Please update to 1.14.1 or newer")


    # --- Send data -----------------------------------------------------------
    with ismrmrd.Dataset(args.filename, info.in_group, create_if_needed=False) as dset:
        logging.info("Sending config: openrecon")
        connection.send_config_file('openrecon')

        xml_header = client.send_MRD_Metadata(connection, dset)

        client.send_additional_config(connection, dset, args.config_json, args.filename)

        # TO-DO: Interleave waveform and other data so they arrive chronologically
        if args.send_waveforms and info.hasWaveforms:
            client.send_waveforms_data(connection, dset)

        if info.hasRaw:
            client.send_raw_data(connection, dset)

        if info.hasImage:
            client.send_image_data(connection, dset, info.in_group)

    # --- Close and wait ------------------------------------------------------
    try:
        connection.send_close()
    except:
        logging.error('Failed to send close message!')

    logging.debug("Waiting for threads to finish")
    process.join()

    sock.close()
    logging.info("Socket closed (writer)")

    # --- Save XML header to output file --------------------------------------
    # Save a copy of the MRD XML header now that the connection thread is 
    # finished with the file
    logging.debug("Writing MRD metadata to file")
    dset = ismrmrd.Dataset(args.outfile, args.out_group)
    dset.write_xml_header(bytes(xml_header, 'utf-8'))
    dset.close()

    logging.info("---------------------- Summary ----------------------")
    logging.info("Sent %5d images        |  Received %5d images", connection.sentImages, recvImages.value)
    logging.info("Results written to %s", args.outfile)
    logging.info("Session complete")


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
    parser.add_argument('-w', '--send-waveforms',     action='store_true', help='Send waveform (physio) data')
    parser.add_argument('-v', '--verbose',            action='store_true', help='Verbose mode')
    parser.add_argument('-l', '--logfile',            type=str,            help='Path to log file')

    parser.set_defaults(**defaults)

    args = parser.parse_args()

    format_log = 'CLIENT : %(levelname)8s: %(message)s'

    if args.logfile:
        print("Logging to file: ", args.logfile)
        logging.basicConfig(filename=args.logfile, format=format_log, level=logging.WARNING)
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
    else:
        print("No logfile provided")
        logging.basicConfig(format=format_log, level=logging.WARNING)

    if args.verbose:
        logging.root.setLevel(logging.DEBUG)
    else:
        logging.root.setLevel(logging.INFO)

    main(args)