#!/bin/python3

from server.connection import Connection
from server.pipeline.pipeline import Pipeline

import logging
import  importlib

def pipeline_factory(connection: Connection, app_name: str, app_directory: str) -> Pipeline | None:
    """Create the pipeline based on the config module"""
    try:
        module = importlib.import_module(app_directory + "." + app_name)
        logging.info(f"Starting config {app_name} in {app_directory} directory")
    except ImportError as e:
        logging.error("Failed to load config '%s' with error:\n  %s", app_name, e)
        pipeline = Pipeline(connection, None)
        return pipeline
    
    pipeline = Pipeline(connection, module)
    return pipeline
