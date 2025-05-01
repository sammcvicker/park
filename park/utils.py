"""
Utility functions for Park.
"""
import psutil
import os
import gc


def get_memory_usage():
    """Get current memory usage in MB."""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return memory_info.rss / 1024 / 1024  # Convert to MB


def force_garbage_collection():
    """Force garbage collection to free memory."""
    gc.collect() 