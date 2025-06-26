"""
ATLAS Open Data Magic Client

This script provides a user-friendly Python client to interact with the ATLAS Open Magic REST API.
It simplifies the process of fetching metadata and file URLs for various datasets and releases
from the ATLAS Open Data project.

Key Features:
- Simple functions to set the active data release (e.g., '2024r-pp').
- Efficient local caching of metadata to minimize API calls.
- Helper functions to retrieve specific dataset information, including file URLs for different
  "skims" (filtered versions of datasets).
- Support for multiple URL protocols (root, https, eos).
- Configuration via environment variables for easy integration into different workflows.

Typical Usage:
    import atlasopenmagic as atom

    # Set the desired release
    atom.set_release('2024r-pp')

    # Get metadata for a specific dataset
    metadata = atom.get_metadata('410470')

    # Get the file URLs for the 'exactly4lep' skim of that dataset
    urls = atom.get_urls('410470', skim='exactly4lep')
    print(urls)
"""

import os
import threading
import requests
import warnings
from pprint import pprint

# --- Global Configuration & State ---

# The active release can be set via the 'ATLAS_RELEASE' environment variable.
# Defaults to '2024r-pp' if the variable is not set.
current_release = os.environ.get('ATLAS_RELEASE', '2024r-pp')

# The API endpoint can be set via the 'ATLAS_API_BASE_URL' environment variable.
# This allows pointing the client to different API instances (e.g., development, production).
API_BASE_URL = os.environ.get('ATLAS_API_BASE_URL', 'https://atlasopenmagic-rest-api-atlas-open-data.app.cern.ch')

# The local cache to store metadata fetched from the API for the current release.
# This dictionary is populated on the first call to get_metadata() for a new release.
_metadata = {}

# A thread lock to ensure that the cache is accessed and modified safely in multi-threaded environments.
_metadata_lock = threading.Lock()

# A user-friendly dictionary describing the available data releases.
RELEASES_DESC = {
    '2016e-8tev': '2016 Open Data for education release of 8 TeV proton-proton collisions (https://opendata.cern.ch/record/3860).',
    '2020e-13tev': '2020 Open Data for education release of 13 TeV proton-proton collisions (https://cern.ch/2r7xt).',
    '2024r-pp': '2024 Open Data for research release for proton-proton collisions (https://opendata.cern.record/80020).',
    '2024r-hi': '2024 Open Data for research release for heavy-ion collisions (https://opendata.cern.ch/record/80035).',
    '2025e-13tev-beta': '2025 Open Data for education and outreach beta release for 13 TeV proton-proton collisions (https://opendata.cern.ch/record/93910).',
    '2025r-evgen': '2025 Open Data for research release for event generation (https://opendata.cern.ch/record/160000).',
}

# Mapping for old, deprecated field names to the new names used in the API.
# This provides backward compatibility for users accustomed to the old naming convention.
COLUMN_MAPPING = {
    'dataset_id': 'dataset_number',
    'short_name': 'physics_short',
    'e-tag': 'e_tag',
    'cross_section': 'cross_section_pb',
    'filter_efficiency': 'genFiltEff',
    'k_factor': 'kFactor',
    'number_events': 'nEvents',
    'sum_weights': 'sumOfWeights',
    'sum_weights_squared': 'sumOfWeightsSquared',
    'process': 'process',
    'generators': 'generator',
    'keywords': 'keywords',
    'description': 'description',
    'job_link': 'job_path',
}

# --- Internal Helper Functions ---

def _apply_protocol(url, protocol):
    """
    Internal helper to transform a root URL into the specified protocol format.
    
    Args:
        url (str): The base 'root://' URL.
        protocol (str): The target protocol ('https', 'eos', or 'root').

    Returns:
        str: The transformed URL.
    """
    if protocol == 'https':
        # Convert to a web-accessible URL via opendata.cern.ch
        return url.replace('root://eospublic.cern.ch:1094/', 'https://opendata.cern.ch')
    elif protocol == 'eos':
        # Provide the path relative to the EOS mount point
        return url.replace('root://eospublic.cern.ch:1094/', '')
    elif protocol == 'root':
        # Return the original URL for direct ROOT access
        return url
    else:
        raise ValueError(f"Invalid protocol '{protocol}'. Must be 'root', 'https', or 'eos'.")

def _fetch_and_cache_release_data(release_name):
    """
    Internal helper to fetch all datasets for a release and populate the local cache.
    This function performs a single, efficient API call to `/releases/{release_name}`
    to minimize network latency.

    Args:
        release_name (str): The name of the release to fetch.

    Raises:
        ValueError: If the API call fails or returns an error.
    """
    global _metadata
    print(f"Fetching and caching all metadata for release: {release_name}...")
    try:
        # Call the API endpoint that returns the full release details, including all datasets.
        response = requests.get(f"{API_BASE_URL}/releases/{release_name}")
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        release_data = response.json()

        # Create a new cache dictionary. This allows for an atomic update of the global cache.
        new_cache = {}
        # Iterate through the datasets returned by the API.
        for dataset in release_data.get('datasets', []):
            # Cache the dataset by its unique number (as a string).
            ds_number_str = str(dataset['dataset_number'])
            new_cache[ds_number_str] = dataset
            # Also cache by the physics short name, if available, for user convenience.
            if dataset.get('physics_short'):
                new_cache[dataset['physics_short']] = dataset
        
        # Atomically replace the global cache with the newly populated one.
        _metadata = new_cache
        print(f"Successfully cached {len(release_data.get('datasets', []))} datasets.")
    except requests.exceptions.RequestException as e:
        # Handle network errors, timeouts, etc.
        raise ValueError(f"Failed to fetch metadata for release '{release_name}' from API: {e}")

# --- Public API Functions ---

# # Commenting this out as it is not currently used. To be decided if we want to keep it.
# def set_api_base_url(api_base_url):
#     """
#     Configures the base URL for the REST API.

#     This is useful for pointing the client to a development or staging API instance.
#     Changing the URL will automatically clear the local cache.

#     Args:
#         api_base_url (str): The new base URL for the API (e.g., 'http://localhost:8000').

#     Raises:
#         ValueError: If the provided URL is not a valid HTTP/HTTPS URL.
#     """
#     global API_BASE_URL
#     if not api_base_url.startswith(('http://', 'https://')):
#         raise ValueError("API base URL must start with 'http://' or 'https://'.")
#     API_BASE_URL = api_base_url
#     # Re-fetch data from the new URL on the next metadata request.
#     set_release(current_release)

def available_releases():
    """
    Displays a list of all available data releases and their descriptions,
    with clean, aligned formatting.
    
    This function prints directly to the console for easy inspection.
    """
    # Find the length of the longest release name to calculate padding.
    max_len = max(len(k) for k in RELEASES_DESC.keys())

    print("Available releases:")
    print("========================================")
    # Use ljust() to pad each release name to the max length for perfect alignment.
    for release, desc in RELEASES_DESC.items():
        print(f"{release.ljust(max_len)}  {desc}")

def get_current_release():
    """
    Returns the name of the currently active data release.

    Returns:
        str: The name of the current release (e.g., '2024r-pp').
    """
    return current_release

def set_release(release):
    """
    Sets the active data release for all subsequent API calls.

    Changing the release will clear the local metadata cache, forcing a re-fetch
    of data from the API upon the next request.

    Args:
        release (str): The name of the release to set as active.

    Raises:
        ValueError: If the provided release name is not valid.
    """
    global current_release, _metadata
    if release not in RELEASES_DESC:
        raise ValueError(f"Invalid release: '{release}'. Use one of: {', '.join(RELEASES_DESC.keys())}")
    
    with _metadata_lock:
        current_release = release
        print(f"Metadata before: {_metadata}")  # Debug: Show the cache
        _metadata = {}  # Invalidate and clear the cache
        print(f"Metadata after: {_metadata}")  # Debug: Show the cleared cache
        print(f"Active release set to: {current_release}. Metadata cache cleared.")

def get_metadata(key, var=None):
    """
    Retrieves metadata for a given dataset, identified by its number or physics short name.

    If the cache is empty for the current release, this function will trigger a fetch
    from the API to populate it.

    Args:
        key (str or int): The dataset identifier (e.g., '410470' or 'ttbar_lep').
        var (str, optional): A specific metadata field to retrieve. If None, the entire
                             metadata dictionary is returned. Supports old and new field names.

    Returns:
        dict or any: The full metadata dictionary for the dataset, or the value of the
                     single field if 'var' was specified.

    Raises:
        ValueError: If the dataset key or the specified variable field is not found.
    """
    global _metadata
    key_str = str(key).strip()
    
    with _metadata_lock:
        # Fetch-on-demand: If the cache is empty, populate it.
        if not _metadata:
            _fetch_and_cache_release_data(current_release)

    # Retrieve the full dataset dictionary from the cache.
    sample_data = _metadata.get(key_str)
    if not sample_data:
        raise ValueError(f"Invalid key: '{key_str}'. No dataset found with this ID or name in release '{current_release}'.")

    # If no specific variable is requested, return the whole dictionary.
    if not var:
        return sample_data
    
    # If a specific variable is requested, try to find it.
    # 1. Check for a direct match with the new API field names.
    if var in sample_data:
        return sample_data.get(var)
    
    # 2. If not found, check the backward compatibility mapping for old field names.
    column_name = COLUMN_MAPPING.get(var.lower())
    if column_name and column_name in sample_data:
        return sample_data.get(column_name)
    
    # 3. If still not found, raise a helpful error listing available fields.
    available_fields = list(sample_data.keys()) + list(COLUMN_MAPPING.keys())
    raise ValueError(f"Invalid field name: '{var}'. Available fields: {', '.join(sorted(set(available_fields)))}")

def get_urls(key, skim='noskim', protocol='root'):
    """
    Retrieves file URLs for a given dataset, with options for skims and protocols.

    This function correctly interprets the structured skim data from the API.

    Args:
        key (str or int): The dataset identifier.
        skim (str, optional): The desired skim type. Defaults to 'noskim' for the base,
                              unfiltered dataset. Other examples: 'exactly4lep', '3lep'.
        protocol (str, optional): The desired URL protocol. Can be 'root', 'https', or 'eos'.
                                  Defaults to 'root'.

    Returns:
        list[str]: A list of file URLs matching the criteria.

    Raises:
        ValueError: If the requested skim or protocol is not available for the dataset.
    """
    # First, get the complete metadata for the dataset.
    dataset = get_metadata(key)
    
    # Now, build a dictionary of all available file lists from the structured API response.
    available_files = {}
    
    # The 'file_list' at the top level corresponds to the 'noskim' version.
    if dataset.get('file_list'):
        available_files['noskim'] = dataset['file_list']
        
    # The 'skims' list contains objects, each with their own 'skim_type' and 'file_list'.
    for skim_obj in dataset.get('skims', []):
        available_files[skim_obj['skim_type']] = skim_obj['file_list']

    # Check if the user-requested skim exists in our constructed dictionary.
    if skim not in available_files:
        available_skims = ', '.join(sorted(available_files.keys()))
        raise ValueError(f"Skim '{skim}' not found for dataset '{key}'. Available skims: {available_skims}")
    
    # Retrieve the correct list of URLs and apply the requested protocol transformation.
    raw_urls = available_files[skim]
    return [_apply_protocol(u, protocol.lower()) for u in raw_urls]

def available_data():
    """
    Returns a sorted list of all available dataset numbers for the current release.

    Returns:
        list[str]: A sorted list of dataset numbers as strings.
    """
    with _metadata_lock:
        # Ensure the cache is populated before reading from it.
        if not _metadata:
            _fetch_and_cache_release_data(current_release)
    
    # The cache contains keys for both dataset numbers and physics short names.
    # We filter to return only the numeric dataset IDs.
    return sorted([k for k in _metadata.keys() if k.isdigit()])

# --- Deprecated Functions (for backward compatibility) ---

def get_urls_data(key, protocol='root'):
    """
    DEPRECATED: Retrieves file URLs for the base (unskimmed) dataset.
    
    Please use get_urls(key, skim='noskim', protocol=protocol) instead.
    """
    warnings.warn("get_urls_data() is deprecated. Please use get_urls() instead.", DeprecationWarning, stacklevel=2)
    return get_urls(key, skim='noskim', protocol=protocol)
