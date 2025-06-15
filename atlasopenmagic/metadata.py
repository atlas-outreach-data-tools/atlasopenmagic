import os
import re
import threading
import requests
import warnings
from pprint import pprint

# Allow the default release to be overridden by an environment variable
current_release = os.environ.get('ATLAS_RELEASE', '2024r-pp')

# Global variables. Default release is set to 2024 pp open data for research
current_release = '2024r-pp' 
_api_cache = {}
_cache_lock = threading.Lock()

# Define API endpoints for different releases
# Keys should be: year + e or r (education/research) + tag (for education the center of mass energy, for research the type of data)
LIBRARY_RELEASES = {
    '2016e-8tev': 'https://opendata.atlas.cern/api/metadata/8tev',
    '2020e-13tev': 'https://opendata.atlas.cern/api/metadata/2020e_13tev',
    '2024r-pp': 'https://opendata.atlas.cern/api/metadata',
    '2025e-13tev-beta': 'https://opendata.atlas.cern/api/metadata/beta'
}

# Description of releases so that users don't have to guess
RELEASES_DESC = {
    '2016e-8tev': '2016 Open Data for education release of 8 TeV proton-proton collisions (https://opendata.cern/record/3860).',
    '2020e-13tev': '2020 Open Data for education release of 13 TeV proton-proton collisions (https://cern.ch/2r7xt).',
    '2024r-pp': '2024 Open Data for research release for proton-proton collisions (https://opendata.cern/record/80020).',
    '2025e-13tev-beta': '2025 Open Data for education and outreach beta release for 13 TeV proton-proton collisions (https://opendata.cern.ch/record/93910).',
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

# Set the API endpoint based on the current release
_API_ENDPOINT = LIBRARY_RELEASES[current_release]

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
    Set the release year and adjust the API endpoint and clear cached data.
    """
    # Global variables that will be used within this function
    global _API_ENDPOINT, _api_cache, current_release

    # Get lock to ensure thread-safe modifications of global variables
    with _cache_lock:

        # Update the current release to the provided one
        current_release = release

        _api_cache.clear()  # Clear cached API responses

        # Get API endpoint for the newly set release
        _API_ENDPOINT = LIBRARY_RELEASES.get(release)

        # If the retrieved endpoint is None, the provided release is invalid
        if _API_ENDPOINT is None:
            raise ValueError(f"Invalid release year: {release}. Use one of: {', '.join(LIBRARY_RELEASES.keys())}")

def get_metadata(key, var=None):
    """
    Retrieve metadata for a given sample key (dataset number or physics short) via API.
    """
    global _api_cache

    # Create cache key for this dataset
    cache_key = f"{current_release}:{key}"
    
    # Check if metadata is already cached
    if cache_key not in _api_cache:
        with _cache_lock:
            # Double-check locking pattern
            if cache_key not in _api_cache:
                _api_cache[cache_key] = _fetch_metadata_from_api(key)

    sample_data = _api_cache[cache_key]
    
    # If the API returned None or empty data: invalid key 
    if not sample_data:
        raise ValueError(f"Invalid key: {key}. Are you looking into the correct release? "
                         f"You are currently using the {current_release} release.")
    
    # If a specific variable is requested get it using the column mapping 
    if var:
        column_name = COLUMN_MAPPING.get(var.lower())
        # Return if found
        if column_name:
            return sample_data.get(column_name)
        # If not found show available variables
        else:
            raise ValueError(f"Invalid field name: {var}. Use one of: {', '.join(COLUMN_MAPPING.keys())}")

    return {user_friendly: sample_data.get(actual_name) for user_friendly, actual_name in COLUMN_MAPPING.items()}

def get_urls(key, skim='noskim', protocol='root'):
    """
    Retrieve URLs corresponding to a given dataset key from the API response file_list.
    For the releases in RELEASE_HAS_SKIMS, an optional parameter 'skim' is used:
      - Only URLs that match the exact skim value (by default, 'noskim') are returned.
      - If the skim value is not found, an error is raised showing the available skim options.
    For other releases, the skim parameter is ignored and all URLs are returned.
    """

    # If they're asking for a skim outside of the places we have them, warn them
    if current_release not in RELEASE_HAS_SKIMS and skim != 'noskim':
        warnings.warn(
            f"Skims are only available in the releases {RELEASE_HAS_SKIMS}; "
            f"in release '{current_release}' all skims are ignored.",
            UserWarning
        )

    # Get metadata from API which includes file_list
    metadata = get_metadata(key)
    if not metadata:
        raise ValueError(f"Invalid key: {key}. Are you sure you're using the correct release ({current_release})?")

    # Get the cached API response which includes file_list
    cache_key = f"{current_release}:{key}"
    if cache_key not in _api_cache:
        raise ValueError(f"No data found for dataset: {key}")
    
    api_response = _api_cache[cache_key]
    file_list = api_response.get('file_list', [])
    
    if not file_list:
        raise ValueError(f"No files found for dataset: {key}")

    # Process based on the release type:
    if current_release in RELEASE_HAS_SKIMS:
        # For releases with skims, organize URLs by detected skims
        skim_mapping = _extract_skims_from_files(file_list, current_release)
        
        if skim not in skim_mapping:
            available_skims = ', '.join(skim_mapping.keys())
            raise ValueError(f"No URLs found for skim: {skim}. Available skim options for this dataset are: {available_skims}.")
        
        raw_urls = skim_mapping[skim]
    else:
        # For all other releases, simply return all URLs
        raw_urls = file_list
    
    # Apply the protocol to the URLs based on the requested protocol.
    proto = protocol.lower()
    if proto not in ('root', 'https'):
        raise ValueError(f"Invalid protocol '{proto}'. Must be 'root' or 'https'.")

    return [_apply_protocol(u, proto) for u in raw_urls]

def available_data():
    """
    Returns a list of available data keys for the current release from the API.
    """
    try:
        response = requests.get(f"{_API_ENDPOINT}/data/available")
        response.raise_for_status()
        data = response.json()
        return data.get('available_keys', [])
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch available data keys for release '{current_release}': {e}")

def get_urls_data(key, protocol='root'):
    """
    Retrieve data URLs corresponding to a given data key from the API
    for the currently selected release.
    """
    try:
        response = requests.get(f"{_API_ENDPOINT}/data/{key}")
        response.raise_for_status()
        data = response.json()
        
        file_list = data.get('file_list', [])
        if not file_list:
            raise ValueError(f"No files found for data key: {key}")
        
        proto = protocol.lower()
        if proto not in ('root', 'https'):
            raise ValueError(f"Invalid protocol '{proto}'. Must be 'root' or 'https'.")

        return [_apply_protocol(u, proto) for u in file_list]
        
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch data for key '{key}' in release '{current_release}': {e}")
    except KeyError:
        raise ValueError(f"Invalid response format from API for data key: {key}")
    except Exception as e:
        # Handle mock exceptions and other errors
        raise ValueError(f"Failed to fetch data for key '{key}' in release '{current_release}': {e}")

#### Internal Helper Functions ####

def _fetch_metadata_from_api(key):
    """
    Fetch metadata for a specific dataset key from the API.
    """
    try:
        response = requests.get(f"{_API_ENDPOINT}/{key}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # Return None for API errors - will be handled by calling function
        return None
    except ValueError as e:
        # Return None for JSON parsing errors
        return None
    except Exception as e:
        # Return None for any other errors (including mock exceptions)
        return None

def _extract_skims_from_files(file_list, release):
    """
    Extract skim information from file URLs and organize them by skim type.
    Returns a dictionary mapping skim names to lists of URLs.
    """
    skim_mapping = {}
    
    # Get the regex pattern for this release
    regex_pattern = REGEX_PATTERNS.get(release)
    if not regex_pattern:
        # If no pattern, treat all files as 'noskim'
        skim_mapping['noskim'] = file_list
        return skim_mapping
    
    regex = re.compile(regex_pattern)
    
    for url in file_list:
        url = url.strip()
        
        if release in RELEASE_HAS_SKIMS:
            # For releases with skims, extract skim from filename
            match = regex.search(url)
            if match and len(match.groups()) >= 2:
                skim_extracted = match.group(2)  # Second group is the skim
            else:
                # If regex doesn't match, check for common skim patterns
                if '.noskim.' in url:
                    skim_extracted = 'noskim'
                else:
                    # Default fallback
                    skim_extracted = 'unknown'
        else:
            # For releases without skims, everything goes to 'noskim'
            skim_extracted = 'noskim'
        
        if skim_extracted not in skim_mapping:
            skim_mapping[skim_extracted] = []
        skim_mapping[skim_extracted].append(url)
    
    return skim_mapping

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