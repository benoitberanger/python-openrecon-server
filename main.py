#!/usr/bin/python3

from server import Server

import argparse
import sys
import signal
import logging


def main(args: argparse.Namespace):
    """Lauch the server"""
    server = Server(args.host, args.port, args.defaultConfig, args.savedata, args.savedataFolder, args.multiprocessing)

    # Trap signal interrupts (e.g. ctrl+c, SIGTERM) and gracefully stop
    def handle_signals(signum, frame):
        print("Received signal interrupt -- stopping server")
        server.socket.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signals)
    signal.signal(signal.SIGINT,  handle_signals)

    # Allow ctrl+c in Windows
    if sys.platform == 'win32':
        signal.signal(signal.SIGINT, signal.SIG_DFL)


if __name__ == "main":
    parser = argparse.ArgumentParser(description='Example server for openRecon')

    parser.add_argument('-p', '--port',            type=int,            help='Port')
    parser.add_argument('-H', '--host',            type=str,            help='Host')
    parser.add_argument('-d', '--defaultConfig',   type=str,            help='Default (fallback) config module')
    parser.add_argument('-v', '--verbose',         action='store_true', help='Verbose output.')
    parser.add_argument('-l', '--logfile',         type=str,            help='Path to log file')

    args = parser.parse_args()

    if args.verbose:
        logLevel = logging.DEBUG
    else:
        logLevel = logging.INFO

    main(args)