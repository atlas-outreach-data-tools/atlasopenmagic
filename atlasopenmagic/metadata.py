from ast import Raise
import threading
import csv
import requests

# Global variables for caching metadata
_metadata = None
_metadata_lock = threading.Lock()
_METADATA_URL = 'https://opendata.atlas.cern/files/metadata.csv'

current_release = '2024r'

LIBRARY_RELEASES = {
    '2016': 'https://gitlab.cern.ch/richarlu/atlas-open-data-website-v2/-/raw/main/static/files/metadata_8tev.csv',
    '2024r': 'https://opendata.atlas.cern/files/metadata.csv',
    # '2020': 'todo',
}

# Mapping of user-friendly names to actual column names
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

def get_metadata(key, var=None):
    """
    Retrieve metadata for a given sample key (dataset number or physics short).

    Parameters:
    - key: The dataset number or physics short name.
    - var: (Optional) User-friendly name of the metadata field to retrieve.

    Returns:
    - If `var` is provided, the value of the specific metadata field, or None if not found.
    - If `var` is not provided, a dictionary containing all metadata fields for the sample, or None if not found.
    """
    global _metadata

    # Ensure metadata is loaded
    if _metadata is None:
        _load_metadata()
    # Retrieve metadata for the given key
    sample_data = _metadata.get(str(key).strip())
    print(sample_data)
    if not sample_data:
        raise ValueError(f"Invalid key: {key}")
        return None

    # Translate user-friendly name to actual column name
    if var:
        column_name = COLUMN_MAPPING.get(var)
        if column_name:
            return sample_data.get(column_name)
        else:
            raise ValueError(f"Invalid field name: {var}. Use one of: {', '.join(COLUMN_MAPPING.keys())}")
    
    # Return the entire metadata dictionary with user-friendly keys
    return {user_friendly: sample_data[actual_name] for user_friendly, actual_name in COLUMN_MAPPING.items()}

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
        data_source = _METADATA_URL
        print(_METADATA_URL)
        # Fetch data from URL
        response = requests.get(data_source)
        response.raise_for_status()
        lines = response.text.splitlines()

        reader = csv.DictReader(lines)
        
        for row in reader:
            dataset_number = row['dataset_number'].strip()
            physics_short = row['physics_short'].strip()
            # Store metadata indexed by dataset_number and physics_short
            _metadata[dataset_number] = row
            _metadata[physics_short] = row

def get_metadata_field(key, field_name, metadata_file=None):
    """
    Retrieve a specific metadata field for a given key.

    Parameters:
    - key: The dataset number or physics short name.
    - field_name: The name of the metadata field to retrieve.
    - metadata_file: Optional path to a local metadata CSV file.

    Returns:
    - The value of the requested metadata field, or None if not found.
    """
    if _metadata is None:
        _load_metadata(metadata_file)

    data = _metadata.get(str(key).strip())
    if data:
        return data.get(field_name)
    else:
        return None

def get_description(key, metadata_file=None):
    """
    Retrieve the description for a given dataset.

    Parameters:
    - key: The dataset number or physics short name.

    Returns:
    - The description string, or None if not found.
    """
    return get_metadata_field(key, 'description', metadata_file)

def set_release(release):
    """
    Set the release year and adjust the metadata source URL or file.
    """
    global _METADATA_URL, _metadata, current_release
    
    with _metadata_lock:
        _metadata = None  # Clear cached metadata
        current_release = release
        _METADATA_URL = LIBRARY_RELEASES.get(release)
        
        if _METADATA_URL is None:
            raise ValueError(f"Invalid release year: {release}. Use one of: {', '.join(LIBRARY_RELEASES.keys())}")
        
        return _METADATA_URL
