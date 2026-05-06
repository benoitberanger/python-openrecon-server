#!/bin/python3

import logging
import os

import psutil


def process_memory_mb() -> float:
    """
    Return the RSS memory of the current process in MB.
    
    Returns
    -------
    float
        Current RSS memory usage of the process in MB.
    """
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1e6


def container_memory_limit_mb() -> float | None:
    """
    Return memory limit in a Docker container (MB), or None if
    not in a Docker container.

    Returns
    -------
    float
        Container memory limit in MB.
    None
        If no limit is set, the cgroup files are not found, or the
        process is not running inside a Docker container.
    """
    cgroup_files = [
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",   # cgroup v1
        "/sys/fs/cgroup/memory.max",                     # cgroup v2
    ]
    
    for path in cgroup_files:
        try:
            with open(path) as f:
                value = f.read().strip()
            if value in ("max", ""):
                return None
            limit = int(value)
            if limit > 1e15:
                return None
            return limit / 1e6
        except (FileNotFoundError, ValueError):
            continue
    return


def memory_limit_mb() -> float:
    """
    Return the total available memory in MB.

    Returns the Docker container memory limit if one is defined
    (see container_memory_limit_mb()), otherwise returns the total
    physical RAM of the host as reported by psutil.

     Returns
    -------
    float
        Available memory ceiling in MB (container limit or host RAM).
    """
    container_limit = container_memory_limit_mb()
    if container_limit is not None:
        return container_limit
    return psutil.virtual_memory().total / 1e6


def log_memory(level: str, label: str = "") -> float:
    """
    Log memory usage of the current process in MB.

    Parameters
    ----------
    level : str
        Coarse-grained stage identifier used to group related log lines,
        e.g. ``'pipeline'``, ``'process_image'``, ``'handle_image_stream'``.
    label : str, optional
        Fine-grained step label within the stage,
        e.g. ``'After stack'``, ``'Beginning process_image'``.
        Default is an empty string.

    Returns
    -------
    float
        Current RSS memory usage in MB.
    """
    mem = process_memory_mb()
    total = memory_limit_mb()
    pct   = 100 * mem / total if total > 0 else 0
    logging.info("RAM [%s] [%s] : %.1f Mo / %.0f Mo (%.1f%%)", level, label, mem, total, pct)
    return mem


def log_memory_delta(level: str, label: str, mem_before: float) -> float:
    """
    Log the current RSS memory usage and the delta from a previous measurement.

    Parameters
    ----------
    level : str
        Coarse-grained stage identifier, same value as used in the
        preceding log_memory() call for consistency.
    label : str
        Fine-grained step label describing what just happened,
        e.g. ``'After astype float32'``, ``'After del images'``.
    mem_before : float
        RSS memory in MB at the previous measurement.

    Returns
    -------
    float
        Current RSS memory usage in MB.
    """
    mem = process_memory_mb()
    total = memory_limit_mb()
    delta = mem - mem_before
    pct   = 100 * mem / total if total > 0 else 0
    logging.info("RAM [%s] [%s] : %.1f Mo / %.0f Mo (%.1f%%)  (%+.1f Mo)", level, label, mem, total, pct, delta)
    return mem
