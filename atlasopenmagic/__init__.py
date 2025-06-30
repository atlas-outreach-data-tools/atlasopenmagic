"""
This module initializes the atlasopenmagic package, providing access to its functionalities.
"""

from .metadata import (
    get_metadata,
    set_release,
    get_urls,
    available_releases,
    get_current_release,
    get_urls_data,
    available_datasets
)

from .utils import (
    install_from_environment,
    build_dataset,
    build_mc_dataset,
    build_data_dataset
)

# List of public functions available when importing the package
__all__ = [
    "get_urls",
    "get_metadata",
    "set_release",
    "available_releases",
    "get_current_release",
    "get_urls_data",
    "available_datasets",
    "install_from_environment",
    "build_dataset",
    "build_mc_dataset",
    "build_data_dataset"
]
