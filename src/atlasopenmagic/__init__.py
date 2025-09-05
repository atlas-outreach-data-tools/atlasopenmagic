"""This module initializes the atlasopenmagic package.

It provides access to its functionalities.
"""

from .metadata import (
    available_datasets,
    available_keywords,
    available_releases,
    available_skims,
    find_all_files,
    get_all_info,
    get_all_metadata,
    get_current_release,
    get_metadata,
    get_metadata_fields,
    get_urls,
    get_urls_data,
    match_metadata,
    read_metadata,
    save_metadata,
    set_release,
)
from .utils import (
    build_data_dataset,
    build_dataset,
    build_mc_dataset,
    install_from_environment,
)

# List of public functions available when importing the package
__all__ = [
    "get_urls",
    "get_metadata",
    "available_skims",
    "get_metadata_fields",
    "set_release",
    "find_all_files",
    "available_releases",
    "get_all_info",
    "get_current_release",
    "get_urls_data",
    "available_datasets",
    "available_keywords",
    "match_metadata",
    "save_metadata",
    "read_metadata",
    "get_all_metadata",
    "install_from_environment",
    "build_dataset",
    "build_mc_dataset",
    "build_data_dataset",
]
