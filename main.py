#!/usr/bin/python3

from server.server import Server

import argparse
import sys
import signal
import logging
import os

defaults = {
    'host':           '0.0.0.0',
    'port':           9002,
    'config':         'invertContrast',
}

def main(args: argparse.Namespace):
    """Lauch the server"""
    server = Server(args.port, args.host, args.config, args.savedata)

    # Trap signal interrupts (e.g. ctrl+c, SIGTERM) and gracefully stop
    def handle_signals(signum, frame) -> None:
        print("Received signal interrupt -- stopping server")
        server.socket.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signals)
    signal.signal(signal.SIGINT,  handle_signals)

    # Allow ctrl+c in Windows
    if sys.platform == 'win32':
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # Start server
    server.serve()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Example server for openRecon')

    parser.add_argument('-p', '--port',            type=int,            help='Port')
    parser.add_argument('-H', '--host',            type=str,            help='Host')
    parser.add_argument('-c', '--config',          type=str,            help='config module')
    parser.add_argument('-v', '--verbose',         action='store_true', help='Verbose output.')
    parser.add_argument('-l', '--logfile',         type=str,            help='Path to log file')
    parser.add_argument('-s', '--savedata',        action='store_true', help='Save incoming data')

    parser.set_defaults(**defaults)

    args = parser.parse_args()

    if args.verbose:
        logLevel = logging.DEBUG
    else:
        logLevel = logging.INFO

    format_log='%(asctime)s - SEVER : %(message)s'

    if args.logfile:
        print("Logging to file:", args.logfile)

        # Get full path to the log file
        absLogPath = os.path.abspath(args.logfile)
        if not os.path.exists(os.path.dirname(absLogPath)):
            os.makedirs(os.path.dirname(absLogPath))

        logging.basicConfig(
            format=format_log,
            level=logLevel,
            handlers=[
                logging.FileHandler(args.logfile),
                logging.StreamHandler(sys.stdout)
            ],
            force=True
        )
    else:
        print("No logfile provided")
        logging.basicConfig(
            format=format_log,
            level=logLevel,
            handlers=[
                logging.StreamHandler(sys.stdout)
            ],
            force=True
        )

    main(args)