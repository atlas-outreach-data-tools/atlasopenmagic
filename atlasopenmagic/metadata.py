import os
import re
import threading
import csv
import requests
from pprint import pprint
from atlasopenmagic.data.id_matches import id_matches, id_matches_8TeV
from atlasopenmagic.data.urls_mc import url_mapping
from atlasopenmagic.data.urls_data import url_mapping_data


# Allow the default release to be overridden by an environment variable
current_release = os.environ.get('ATLAS_RELEASE', '2024r-pp')

# Global variables. Default release is set to 2024 pp open data for research
current_release = '2024r-pp' 
_metadata = None
_metadata_lock = threading.Lock()
_url_code_mapping = None
_mapping_lock = threading.Lock()

# Define releases
# Keys should be: year + e or r (education/research) + tag (for education the center of mass energy, for research the type of data)
LIBRARY_RELEASES = {
    '2016e-8tev': 'https://opendata.atlas.cern/files/metadata_8tev.csv',
    '2024r-pp': 'https://opendata.atlas.cern/files/metadata.csv',
}

# Description of releases so that users don't have to guess
RELEASES_DESC = {
    '2016e-8tev': '2016 Open Data for education release for 8 TeV pp collisions.',
    '2024r-pp': '2024 Open Data for research release for proton-proton collisions.'
}

# Mapping of releases to their id match dictionaries
ID_MATCH_LOOKUP = {
    '2024r-pp': id_matches,
    '2016e-8tev': id_matches_8TeV
}

# Paths to the list of xrootd URLs for different releases 
FILE_PATHS = {
    "2024r-pp": os.path.join(os.path.dirname(__file__), 'data', 'urls.txt'), 
    "2016e-8tev": os.path.join(os.path.dirname(__file__), 'data', 'urls_TeV8.txt'),
}

# Define naming convention for datasets for different releases
REGEX_PATTERNS = {
    "2024r-pp": r'DAOD_PHYSLITE\.(\d+)\.', # Capture the () from DAOD_PHYSLITE.(digits).
    "2016e-8tev": r'mc_(\d+)\.' # Capture the () from mc_(digits)
}

# The columns of the metadata file are not great, let's use nicer ones for coding (we should probably change the metadata insted?)
# ALL keys must be lowercase!
COLUMN_MAPPING = {
    'dataset_id': 'dataset_number',
    'short_name': 'physics_short',
    'e-tag': 'e-tag',
    'cross_section': 'crossSection_pb',
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

# Set the metadata URL based on the current release
_METADATA_URL = LIBRARY_RELEASES[current_release]

# People need to be able to get information about the releases
def available_releases():
    """
    Returns a list of valid release keys that can be set, and their description.
    """
    pprint(RELEASES_DESC)

def get_current_release():
    """
    Returns the currently set release.
    """
    return current_release

def set_release(release):
    """
    Set the release year and adjust the metadata source URL and cached data.
    """
    # Global variables that will be used within this function
    global _METADATA_URL, _metadata, _url_code_mapping, current_release

    # Get locks to ensure thread-safe modifications of global variables
    with _metadata_lock, _mapping_lock:

        # Update the current release to the provided one
        current_release = release

        _metadata = None  # Clear cached metadata
        _url_code_mapping = None  # Clear cached URL mapping

        # Get metadata URL for the newly set release
        _METADATA_URL = LIBRARY_RELEASES.get(release)

        # If the retrieved URL is None, the provided release is invalid
        if _METADATA_URL is None:
            raise ValueError(f"Invalid release year: {release}. Use one of: {', '.join(LIBRARY_RELEASES.keys())}")

def get_metadata(key, var=None):
    """
    Retrieve metadata for a given sample key (dataset number or physics short).
    """
    global _metadata

    # Check if metadata is already loaded
    if _metadata is None:
        _load_metadata()

    # Try to get the metadata for the given key
    sample_data = _metadata.get(str(key).strip())
    
    # If the key is not found: invalid key and show the user the set release
    if not sample_data:
        raise ValueError(f"Invalid key: {key}. Are you looking into the correct release? "
                         f"You are currently using the {current_release} release.")
    
    # If a specific variable is requested get it using the column mapping 
    if var:
        column_name = COLUMN_MAPPING.get(var.lower())
        # Return if found
        if column_name:
            return sample_data.get(column_name)
        # If not found show available varibles
        else:
            raise ValueError(f"Invalid field name: {var}. Use one of: {', '.join(COLUMN_MAPPING.keys())}")

    return {user_friendly: sample_data[actual_name] for user_friendly, actual_name in COLUMN_MAPPING.items()}

def get_urls(key):
    """
    Retrieve URLs corresponding to a given key from the cached mapping.
    """
    global _url_code_mapping

    # Check if URL mapping is already loaded
    if _url_code_mapping is None:
        _load_url_code_mapping()

    lookup = ID_MATCH_LOOKUP.get(current_release)
    # If the release is not in the possible releases, raise an error
    if lookup is None:
        raise ValueError(f"Unsupported release: {current_release}. Check the available releases with `available_releases()`.")
    
    # Get the value url(s) from the ID match dictionary
    value = lookup.get(str(key))
    # If the key is not found, raise an error
    if not value:
        raise ValueError(f"Invalid key: {key}. Are you sure you're using the correct release ({current_release})?")
    
    return _url_code_mapping.get(value, [])

def available_data():
    """
    Returns a list of available data keys for the current release from the url_mapping_data.
    """
    current_data_mapping = url_mapping_data.get(current_release)
    # If the current release is not found in the url_mapping_data, raise an error
    if current_data_mapping is None:
        raise ValueError(f"Unsupported release: {current_release}. Check the available releases with `available_releases()`.")
    return list(current_data_mapping.keys())

def get_urls_data(key):
    """
    Retrieve data URLs corresponding to a given data key from the url_mapping_data
    for the currently selected release.
    """
    # Check if the key is valid for the current release
    current_data_mapping = url_mapping_data.get(current_release)
    if current_data_mapping is None:
        raise ValueError(f"Current release '{current_release}' not found in url_mapping_data.")
    
    # Get the URLs for the given key
    urls = current_data_mapping.get(key)
    # If the key is not found, raise an error
    if urls is None:
        available_keys = ', '.join(current_data_mapping.keys())
        raise ValueError(f"Invalid data key: {key}. Available keys for release '{current_release}' are: {available_keys}.")
    
    return urls

#### Internal Helper Functions ####

def _load_metadata():
    """
    Load metadata from the CSV file or URL and cache it.
    """
    global _metadata
    # Check if metadata is already loaded and avoid reloading
    if _metadata is not None:
        return

    # Double-checked locking
    with _metadata_lock:
        if _metadata is not None:
            return  

        # Load metadata from the URL
        _metadata = {}
        response = requests.get(_METADATA_URL)
        # Raise an error if the request was unsuccessful
        response.raise_for_status()
        # Split the response text into lines
        lines = response.text.splitlines()

        # Read the CSV data using DictReader
        reader = csv.DictReader(lines)
        for row in reader:
            # Strip whitespace and fill the _metadata dictionary
            dataset_number = row['dataset_number'].strip()
            physics_short = row['physics_short'].strip()
            _metadata[dataset_number] = row
            # We can use the physics short name to get the metadata as well
            _metadata[physics_short] = row

def _load_url_code_mapping():
    """
    Load URLs from the url_mapping dictionary in data/urls_mc.py and build a mapping from dataset codes to URLs
    for the currently selected release.
    """
    global _url_code_mapping

    # Avoid reloading if already done
    if _url_code_mapping is not None:
        return

    with _mapping_lock:
        if _url_code_mapping is not None:
            return  

        # Retrieve the list of URLs for the current release.
        urls = url_mapping.get(current_release)
        if urls is None:
            raise ValueError(f"Unsupported release: {current_release}. Check the available releases with `available_releases()`.")

        # Initialize the mapping dictionary.
        _url_code_mapping = {}

        # Select the regex pattern based on the release.
        if current_release == '2024r-pp':
            regex_pattern = REGEX_PATTERNS["2024r-pp"]
        elif current_release == '2016e-8tev':
            regex_pattern = REGEX_PATTERNS.get("2016e-8tev")
        
        regex = re.compile(regex_pattern)

        # Process each URL in the list.
        for url in urls:
            url = url.strip()
            match = regex.search(url)
            if match:
                code = match.group(1)
                _url_code_mapping.setdefault(code, []).append(url)
