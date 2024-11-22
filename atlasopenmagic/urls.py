import os
import re
import threading
from atlasopenmagic.data.id_matches import id_matches

# Global variables for caching URLs
_url_code_mapping = None
_mapping_lock = threading.Lock()

# Path to the URL file (relative to this module)
_URL_FILE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'urls.txt')

def _load_url_code_mapping():
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

        # Open the file using the predefined path
        with open(_URL_FILE_PATH, 'r') as f:
            for line in f:
                url = line.strip()
                match = pattern.search(url)
                if match:
                    code = match.group(1)
                    _url_code_mapping.setdefault(code, []).append(url)

def get_urls(key):
    """
    Find URLs corresponding to a given key.

    Parameters:
    - key: The key to search for (as a string or integer).

    Returns:
    - A list of URLs matching the key.
    """
    # Load the URL-code mapping if not already loaded
    if _url_code_mapping is None:
        _load_url_code_mapping()

    value = id_matches.get(str(key))
    if not value:
        return []

    # Retrieve URLs corresponding to the value
    return _url_code_mapping.get(value, [])
