import os
import re
import threading
import csv
import requests
from atlasopenmagic.data.id_matches import id_matches, id_matches_8TeV

# Global variables
current_release = '2024r'
_metadata = None
_metadata_lock = threading.Lock()
_url_code_mapping = None
_mapping_lock = threading.Lock()

LIBRARY_RELEASES = {
    '2016': 'https://opendata.atlas.cern/files/metadata_8tev.csv',
    '2024r': 'https://opendata.atlas.cern/files/metadata.csv',
}

FILE_PATHS = {
    "standard": os.path.join(os.path.dirname(__file__), 'data', 'urls.txt'),
    "tev8": os.path.join(os.path.dirname(__file__), 'data', 'urls_TeV8.txt'),
}

REGEX_PATTERNS = {
    "standard": r'DAOD_PHYSLITE\.(\d+)\.',
    "tev8": r'mc_(\d+)\.|Data(\d+)\.',
}

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

_METADATA_URL = LIBRARY_RELEASES[current_release]


def set_release(release):
    """
    Set the release year and adjust the metadata source URL and cached data.
    """
    global _METADATA_URL, _metadata, _url_code_mapping, current_release

    with _metadata_lock, _mapping_lock:
        global current_release
        current_release = release
        _metadata = None  # Clear cached metadata
        _url_code_mapping = None  # Clear cached URL mapping
        _METADATA_URL = LIBRARY_RELEASES.get(release)

        if _METADATA_URL is None:
            raise ValueError(f"Invalid release year: {release}. Use one of: {', '.join(LIBRARY_RELEASES.keys())}")


def get_metadata(key, var=None):
    """
    Retrieve metadata for a given sample key (dataset number or physics short).
    """
    global _metadata

    if _metadata is None:
        _load_metadata()

    sample_data = _metadata.get(str(key).strip())
    if not sample_data:
        raise ValueError(f"Invalid key: {key}. Are you looking into the correct release?")

    if var:
        column_name = COLUMN_MAPPING.get(var)
        if column_name:
            return sample_data.get(column_name)
        else:
            raise ValueError(f"Invalid field name: {var}. Use one of: {', '.join(COLUMN_MAPPING.keys())}")

    return {user_friendly: sample_data[actual_name] for user_friendly, actual_name in COLUMN_MAPPING.items()}


def get_urls(key):
    """
    Retrieve URLs corresponding to a given key from the cached mapping.
    """
    global _url_code_mapping

    if _url_code_mapping is None:
        _load_url_code_mapping()

    if current_release == '2024r':
        value = id_matches.get(str(key))
        if not value:
            raise ValueError(f"Invalid key: {key}. You are looking into the 2024r release, are you sure it's the correct one?")
    elif current_release == '2016':
        value = id_matches_8TeV.get(str(key))
        if not value:
            raise ValueError(f"Invalid key: {key}. You are looking into the 2016 release, are you sure it's the correct one?")
    else:
        value = None

    return _url_code_mapping.get(value, [])


#### Internal Helper Functions ####

def _load_metadata():
    """
    Load metadata from the CSV file or URL and cache it.
    """
    global _metadata
    if _metadata is not None:
        return

    with _metadata_lock:
        if _metadata is not None:
            return  # Double-checked locking

        _metadata = {}
        response = requests.get(_METADATA_URL)
        response.raise_for_status()
        lines = response.text.splitlines()

        reader = csv.DictReader(lines)
        for row in reader:
            dataset_number = row['dataset_number'].strip()
            physics_short = row['physics_short'].strip()
            _metadata[dataset_number] = row
            _metadata[physics_short] = row


def _load_url_code_mapping():
    """
    Load URLs from multiple files and build a mapping from codes to URLs.
    """
    global _url_code_mapping
    if _url_code_mapping is not None:
        return

    with _mapping_lock:
        if _url_code_mapping is not None:
            return  # Double-checked locking

        _url_code_mapping = {}
        for key, file_path in FILE_PATHS.items():
            if key in REGEX_PATTERNS:
                regex_pattern = REGEX_PATTERNS[key]
                regex = re.compile(regex_pattern)

                with open(file_path, 'r') as f:
                    for line in f:
                        url = line.strip()
                        match = regex.search(url)
                        if match:
                            code = match.group(1) or match.group(2)
                            _url_code_mapping.setdefault(code, []).append(url)
