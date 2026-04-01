#!/bin/python3

from server.connection import Connection
from server.pipeline.pipeline import Pipeline

import logging
import  importlib

def pipeline_factory(connection: Connection, config_name: str) -> Pipeline | None:
    """Create the pipeline based on the config module"""
    try:
        module = importlib.import_module("app."+config_name)
        logging.info(f"Starting config {config_name}")
    except ImportError as e:
        logging.error("Failed to load config '%s' with error:\n  %s", config_name, e)
        return
    
    pipeline = Pipeline(connection, module)
    return pipeline
