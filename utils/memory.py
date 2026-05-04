#!/bin/python3

import logging
import os

import psutil


def _process_memory_mb() -> float:
    """Return the RSS memory of the current process in Mo"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1e6


def _container_memory_limit_mb() -> float | None:
    """
    Return memory limit in a Docker container (Mo), or None if
    not in a Docker container
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


def _memory_limit_mb() -> float:
    """
    Return total free memory in Mo.
    Limit for Docker or total host RAM
    """
    container_limit = _container_memory_limit_mb()
    if container_limit is not None:
        return container_limit
    return psutil.virtual_memory().total / 1e6


def log_memory(level: str, label: str = "") -> float:
    """
    Log memory usage of the current process in Mo
    Return the value in Mo
    """
    mem = _process_memory_mb()
    total = _memory_limit_mb()
    pct   = 100 * mem / total if total > 0 else 0
    logging.info("RAM [%s] [%s] : %.1f Mo / %.0f Mo (%.1f%%)", level, label, mem, total, pct)
    return mem


def log_memory_delta(level: str, label: str, mem_before: float) -> float:
    """
    Log memory usage of the current process in Mo and
    the delta with the previous memory usage (mem_before)
    Return memory usage in Mo
    """
    mem = _process_memory_mb()
    total = _memory_limit_mb()
    delta = mem - mem_before
    pct   = 100 * mem / total if total > 0 else 0
    logging.info("RAM [%s] [%s] : %.1f Mo / %.0f Mo (%.1f%%)  (%+.1f Mo)", level, label, mem, total, pct, delta)
    return mem
