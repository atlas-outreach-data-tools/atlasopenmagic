from .metadata import (
    get_metadata,
    set_release,
    get_urls,
    available_releases,
    get_current_release,
    get_urls_data,
    available_data
)

from .notebooks import (
    install_from_environment
)

# List of public functions available when importing the package
__all__ = [
    "get_urls",
    "get_metadata",
    "set_release",
    "available_releases",
    "get_current_release",
    "get_urls_data",
    "available_data",
    "install_from_environment"
]