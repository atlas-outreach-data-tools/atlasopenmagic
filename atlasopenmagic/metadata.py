import threading
import csv
import requests

# Global variables for caching metadata
_metadata = None
_metadata_lock = threading.Lock()
_METADATA_URL = 'https://opendata.atlas.cern/files/metadata.csv'

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
    if not sample_data:
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
<<<<<<< HEAD

def get_metadata(key, metadata_file=None):
    """
    Retrieve the entire metadata row for a given key.

    Parameters:
    - key: The dataset number or physics short name.
    - metadata_file: Optional path to a local metadata CSV file.

    Returns:
    - A dictionary containing all metadata fields, or None if not found.
    """
    if _metadata is None:
        _load_metadata(metadata_file)

    return _metadata.get(str(key).strip())

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

def get_cross_section(key, metadata_file=None):
    """
    Retrieve the cross-section for a given dataset.

    Parameters:
    - key: The dataset number or physics short name.

    Returns:
    - The cross-section in pb, or None if not found.
    """
    cross_section = get_metadata_field(key, 'crossSection_pb', metadata_file)
    if cross_section is not None:
        return float(cross_section)
    else:
        return None

def get_k_factor(key, metadata_file=None):
    """
    Retrieve the k-factor for a given dataset.

    Parameters:
    - key: The dataset number or physics short name.

    Returns:
    - The k-factor, or None if not found.
    """
    k_factor = get_metadata_field(key, 'kFactor', metadata_file)
    if k_factor is not None:
        return float(k_factor)
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
    global _METADATA_URL, _metadata
    with _metadata_lock:
        _metadata = None  # Clear cached metadata
        _METADATA_URL = f'https://opendata.atlas.cern/files/{release}_metadata.csv'
=======
>>>>>>> upstream/main
