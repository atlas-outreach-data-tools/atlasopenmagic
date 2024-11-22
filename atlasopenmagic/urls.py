import os
import re
import threading
from atlasopenmagic.data.id_matches import id_matches

# Global variables for caching URLs
_url_code_mapping = None
_mapping_lock = threading.Lock()

# Paths to the URL files
_URL_FILE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'urls.txt')
_URL_FILE_PATH_TeV8 = os.path.join(os.path.dirname(__file__), 'data', 'urls_TeV8.txt')


def _load_url_code_mapping(file_path, pattern):
    """
    Load URLs from the specified file and build a mapping from code to URLs.

    Parameters:
    - file_path: The path to the file containing the URLs.
    - pattern: A regex pattern to extract codes from URLs.

    Returns:
    - A dictionary mapping codes to lists of URLs.
    """
    mapping = {}
    regex = re.compile(pattern)

    # Open the file and process its lines
    with open(file_path, 'r') as f:
        for line in f:
            url = line.strip()
            match = regex.search(url)
            if match:
                code = match.group(1)
                mapping.setdefault(code, []).append(url)
    
    return mapping


def _initialize_mappings():
    """
    Initialize URL mappings for both standard and TeV8 cases.
    This function is thread-safe.
    """
    global _url_code_mapping
    if _url_code_mapping is not None:
        return

    with _mapping_lock:
        if _url_code_mapping is not None:  # Double-checked locking
            return

        # Load mappings with different patterns for standard and TeV8 files
        standard_mapping = _load_url_code_mapping(_URL_FILE_PATH, r'DAOD_PHYSLITE\.(\d+)\.')
        tev8_mapping = _load_url_code_mapping(_URL_FILE_PATH_TeV8, r'mc_(\d+)\.')

        # Combine the mappings (TeV8 URLs override standard ones if keys overlap)
        _url_code_mapping = {**standard_mapping, **tev8_mapping}


def get_urls(key):
    """
    Find URLs corresponding to a given key.

    Parameters:
    - key: The key to search for (as a string or integer).

    Returns:
    - A list of URLs matching the key.
    """
    # Load the URL-code mappings if not already loaded
    if _url_code_mapping is None:
        _initialize_mappings()

    value = id_matches.get(str(key))
    if not value:
        return []

    # Retrieve URLs for the key
    return _url_code_mapping.get(value, [])