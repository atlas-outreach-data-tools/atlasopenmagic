import os
import re
import threading
from .id_matches import id_matches

# Global variables for caching URLs
_url_code_mapping = None
_mapping_lock = threading.Lock()

def _load_url_code_mapping(url_file='urls.txt'):
    """
    Load URLs from the file and build a mapping from code to URLs.
    This function is intended to be called internally.
    """
    global _url_code_mapping
    if _url_code_mapping is not None:
        return

    with _mapping_lock:
        if _url_code_mapping is not None:
            return  # Double-checked locking

        _url_code_mapping = {}
        pattern = re.compile(r'DAOD_PHYSLITE\.(\d+)\.')

        # Construct the full path to the URL file
        base_dir = os.path.dirname(__file__)
        url_file_path = os.path.join(base_dir, url_file)

        # Open the file using the full path
        with open(url_file_path, 'r') as f:
            for line in f:
                url = line.strip()
                match = pattern.search(url)
                if match:
                    code = match.group(1)
                    _url_code_mapping.setdefault(code, []).append(url)

def get_urls(key, url_file='urls.txt'):
    """
    Find URLs corresponding to a given key.

    Parameters:
    - key: The key to search for (as a string or integer).
    - url_file: The path to the file containing URLs.

    Returns:
    - A list of URLs matching the key.
    """
    # Load the URL-code mapping if not already loaded
    if _url_code_mapping is None:
        _load_url_code_mapping(url_file)

    value = id_matches.get(str(key))
    if not value:
        return []

    # Retrieve URLs corresponding to the value
    return _url_code_mapping.get(value, [])
