#!/bin/python3

import logging
import os
import psutil


def _process_memory_mb() -> float:
    """Return the RSS memory of the current process in Mo"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1e6


def log_memory(label: str = "") -> float:
    """
    Log memory usage of the current process in Mo
    Return the value in Mo
    """
    mem = _process_memory_mb()
    logging.info("RAM [%s] : %.1f Mo", label, mem)
    return mem


def log_memory_delta(label: str, mem_before: float) -> float:
    """
    Log memory usage of the current process in Mo and
    the delta with the previous memory usage (mem_before)
    Return memory usage in Mo
    """
    mem = _process_memory_mb()
    delta = mem - mem_before
    logging.info("RAM [%s] : %.1f Mo  (%+.1f Mo)", label, mem, delta)
    return mem
