import threading
import csv
import requests
from collections import defaultdict

# Global variables for caching metadata
_metadata = None
_metadata_lock = threading.Lock()
_METADATA_URL = 'https://opendata.atlas.cern/files/metadata.csv'

#### METADATA ####
def _load_metadata(metadata_file=None):
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
        data_source = metadata_file or _METADATA_URL

        # Read from URL or local file
        if data_source.startswith('http'):
            response = requests.get(data_source)
            response.raise_for_status()
            lines = response.text.splitlines()
        else:
            with open(data_source, 'r') as f:
                lines = f.readlines()

        reader = csv.DictReader(lines)
        for row in reader:
            dataset_number = row['dataset_number'].strip()
            physics_short = row['physics_short'].strip()
            # Store metadata indexed by dataset_number and physics_short
            _metadata[dataset_number] = row
            _metadata[physics_short] = row

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
