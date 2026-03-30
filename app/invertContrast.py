#!/bin/python3

from server.connection import Connection
import ismrmrd
import numpy as np
import logging

def process_image(images: list, connection: Connection, config: str, metadata: str):
    print("test")
    return images