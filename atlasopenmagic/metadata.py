import os
import re
import threading
import csv
import requests
import warnings
from pprint import pprint
from atlasopenmagic.data.id_matches import id_matches, id_matches_8TeV, id_matches_13TeV2020, id_matches_13TeVbeta
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
    '2020e-13tev': 'https://opendata.atlas.cern/files/metadata_2020e_13tev.csv',
    '2024r-pp': 'https://opendata.atlas.cern/files/metadata.csv',
    '2025e-13tev-beta': 'https://opendata.atlas.cern/files/metadata.csv'
}

# Description of releases so that users don't have to guess
RELEASES_DESC = {
    '2016e-8tev': '2016 Open Data for education release of 8 TeV proton-proton collisions (https://opendata.cern/record/3860).',
    '2020e-13tev': '2020 Open Data for education release of 13 TeV proton-proton collisions (https://cern.ch/2r7xt).',
    '2024r-pp': '2024 Open Data for research release for proton-proton collisions (https://opendata.cern/record/80020).',
    '2025e-13tev-beta': '2025 Open Data for education and outreach beta release for 13 TeV proton-proton collisions (https://opendata.cern.ch/record/93910).',
}

# Mapping of releases to their id match dictionaries
ID_MATCH_LOOKUP = {
    '2024r-pp': id_matches,
    '2016e-8tev': id_matches_8TeV,
    '2020e-13tev': id_matches_13TeV2020,
    '2025e-13tev-beta': id_matches_13TeVbeta
}

# Define naming convention for datasets for different releases
REGEX_PATTERNS = {
    "2024r-pp": r'DAOD_PHYSLITE\.(\d+)\.', # Capture the () from DAOD_PHYSLITE.(digits).
    "2016e-8tev": r'mc_(\d+)\.', # Capture the () from mc_(digits)
    "2020e-13tev": r'mc_(\d+).*?\.([^.]+)\.root$', # Capture the () from mc_(digits) and the skim from the text between the last dot and ".root"
    "2025e-13tev-beta": r'mc_(\d+).*?\.([^.]+)\.root$' # Capture the () from mc_(digits) and the skim from the text between the last dot and ".root"
}

RELEASE_HAS_SKIMS = [ '2020e-13tev' , '2025e-13tev-beta' ]

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

def get_urls(key, skim='noskim', protocol='root'):
    """
    Retrieve URLs corresponding to a given dataset key from the cached URL mapping.
    For the releases in RELEASE_HAS_SKIMS, an optional parameter 'skim' is used:
      - Only URLs that match the exact skim value (by default, 'noskim') are returned.
      - If the skim value is not found, an error is raised showing the available skim options.
    For other releases, the skim parameter is ignored and all URLs are returned.
    """

    # If they're asking for a skim outside of the places we have them, warn them
    if current_release not in RELEASE_HAS_SKIMS and skim != 'noskim':
        warnings.warn(
            f"Skims are only availabe in the releases {RELEASE_HAS_SKIMS}; "
            f"in release '{current_release}' all skims are ignored.",
            UserWarning
        )

    global _url_code_mapping

    # Check if the URL mapping cache has been loaded; if not, load it.
    if _url_code_mapping is None:
        _load_url_code_mapping()

    # Retrieve the mapping lookup dictionary corresponding to the current release.
    lookup = ID_MATCH_LOOKUP.get(current_release)
    if lookup is None:
        raise ValueError(f"Unsupported release: {current_release}. Check the available releases with `available_releases()`.")

    # Use the lookup dictionary to get the unique dataset identifier for the provided key.
    value = lookup.get(str(key))
    if not value:
        raise ValueError(f"Invalid key: {key}. Are you sure you're using the correct release ({current_release})?")

    # Process based on the release type:
    if current_release in RELEASE_HAS_SKIMS:
        # For the releases with skims, the URL mapping is organized as a nested dictionary:
        #   { dataset_code: { skim: [url, ...], ... } }
        mapping = _url_code_mapping.get(value)
        if mapping is None:
            # Raise an error if there is no URL mapping for the determined dataset code.
            raise ValueError(f"No URLs found for dataset id: {value}")
        if skim not in mapping:
            # If the requested skim does not exist, raise an error listing available skims.
            available_skims = ', '.join(mapping.keys())
            raise ValueError(f"No URLs found for skim: {skim}. Available skim options for this dataset are: {available_skims}.")
        # Return only the URLs matching the requested skim.
        raw_urls = mapping[skim]
    else:
        # For all other releases, simply return the list of URLs associated with the dataset code.
        raw_urls = _url_code_mapping.get(value, [])
    
    # Apply the protocol to the URLs based on the requested protocol.
    proto = protocol.lower()
    if proto not in ('root', 'https'):
        raise ValueError(f"Invalid protocol '{proto}'. Must be 'root' or 'https'.")

    return [_apply_protocol(u, proto) for u in raw_urls]

def available_data():
    """
    Returns a list of available data keys for the current release from the url_mapping_data.
    """
    current_data_mapping = url_mapping_data.get(current_release)
    # If the current release is not found in the url_mapping_data, raise an error
    if current_data_mapping is None:
        raise ValueError(f"Unsupported release: {current_release}. Check the available releases with `available_releases()`.")
    return list(current_data_mapping.keys())

def get_urls_data(key, protocol='root'):
    """
    Retrieve data URLs corresponding to a given data key from the url_mapping_data
    for the currently selected release.
    """
    # Check if the key is valid for the current release
    current_data_mapping = url_mapping_data.get(current_release)
    if current_data_mapping is None:
        raise ValueError(f"Current release '{current_release}' not found in url_mapping_data.")

     # Branch on release to decide whether `key` is a skim or a data_key
    if current_release in RELEASE_HAS_SKIMS:
        skim = key
        available = ', '.join(current_data_mapping.keys())
        raw_urls = current_data_mapping.get(skim)
        if raw_urls is None:
            raise ValueError(f"Invalid skim '{skim}'. Available skims: {available}.")
    else:
        data_key = key
        available = ', '.join(current_data_mapping.keys())
        raw_urls = current_data_mapping.get(data_key)
        if raw_urls is None:
            raise ValueError(f"Invalid data key '{data_key}'. Available data keys: {available}.")
    
    # If the key is not found, raise an error
    if raw_urls is None:
        available_keys = ', '.join(current_data_mapping.keys())
        raise ValueError(f"Invalid data key: {key}. Available keys for release '{current_release}' are: {available_keys}.")
    
    proto = protocol.lower()
    if proto not in ('root', 'https'):
        raise ValueError(f"Invalid protocol '{proto}'. Must be 'root' or 'https'.")

    return [_apply_protocol(u, proto) for u in raw_urls]

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
    Load URLs from the url_mapping dictionary and build a mapping from dataset codes to URLs
    for the currently selected release. For the releases in RELEASE_HAS_SKIMS, the function uses
    a unified regex to extract both the dataset id (from the "mc_<digits>" part) and the skim 
    tag (the text between the last dot and ".root") from the URLs.
    """
    global _url_code_mapping

    # Avoid reloading the URL mapping if it is already built
    if _url_code_mapping is not None:
        return

    # Acquire a lock to ensure thread-safe modifications of the URL mapping cache
    with _mapping_lock:
        # Check again to be sure that the URL mapping hasn't been loaded in a concurrent thread
        if _url_code_mapping is not None:
            return  

        # Retrieve the list of URLs for the current release from the global url_mapping dictionary.
        urls = url_mapping.get(current_release)
        if urls is None:
            raise ValueError(f"Unsupported release: {current_release}. Check the available releases with `available_releases()`.")

        # Initialize the URL code mapping cache
        _url_code_mapping = {}

        # For '2024r-pp' and '2016e-8tev', use the existing regex-based extraction logic.
        if current_release in ('2024r-pp', '2016e-8tev'):
            regex_pattern = REGEX_PATTERNS.get(current_release)
            regex = re.compile(regex_pattern)
            # Process each URL: strip whitespace, apply the regex, and populate the mapping with the extracted dataset id.
            for url in urls:
                url = url.strip()
                match = regex.search(url)
                if match:
                    code = match.group(1)
                    _url_code_mapping.setdefault(code, []).append(url)

        # For the releases with skims, use a unified regex that focuses on the DID
        # and extracts the skim tag.
        elif current_release in RELEASE_HAS_SKIMS:
            # The regex should be defined in REGEX_PATTERNS under the key for the release
            # and is expected to capture two groups: 
            #   1. dataset id from "mc_<digits>"
            #   2. skim tag from the last dot before ".root"
            regex_pattern = REGEX_PATTERNS.get(current_release)
            regex = re.compile(regex_pattern)
            # Iterate over each URL, clean it, and attempt to extract dataset id and skim.
            for url in urls:
                url = url.strip()
                match = regex.search(url)
                if match:
                    code = match.group(1)             # Extract dataset id from the first group.
                    skim_extracted = match.group(2)     # Extract skim tag from the second group.
                    # Build a nested mapping: dataset id -> { skim: [url, ...] }
                    if code not in _url_code_mapping:
                        _url_code_mapping[code] = {}
                    _url_code_mapping[code].setdefault(skim_extracted, []).append(url)
        else:
            # Raise an error if the current release is not recognized.
            raise ValueError(f"Unsupported release: {current_release}.")

def _apply_protocol(url, protocol):
    """
    If protocol=='https', rewrite the EOS root URL to HTTPS;
    if protocol=='root', return the URL unchanged.
    """
    if protocol == 'https':
        return url.replace(
            'root://eospublic.cern.ch',
            'https://opendata.cern.ch'
        )
    return url