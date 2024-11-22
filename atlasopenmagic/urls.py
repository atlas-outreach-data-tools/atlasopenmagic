import os
import re
import threading
from atlasopenmagic.data.id_matches import id_matches

# Global variables for caching URLs
_url_code_mapping = None
_mapping_lock = threading.Lock()

# File paths and patterns configuration
FILE_PATHS = {
    "standard": os.path.join(os.path.dirname(__file__), 'data', 'urls.txt'),
    "tev8": os.path.join(os.path.dirname(__file__), 'data', 'urls_TeV8.txt'),
}

REGEX_PATTERNS = {
    "standard": r'DAOD_PHYSLITE\.(\d+)\.',
    "tev8": r'mc_(\d+)\.|Data(\d+)\.',
}

def _load_url_code_mapping():
    """
    Load URLs from multiple files and build a mapping from codes to URLs.
    This function will only run once to initialize the mapping.
    """
    global _url_code_mapping
    if _url_code_mapping is not None:
        return  # If already loaded, return early

    with _mapping_lock:
        if _url_code_mapping is not None:
            return  # Double-checked locking to ensure only one thread initializes

        _url_code_mapping = {}

        # Loop over each file path and regex pattern and extract URLs
        for key, file_path in FILE_PATHS.items():
            if key in REGEX_PATTERNS:
                regex_pattern = REGEX_PATTERNS[key]
                regex = re.compile(regex_pattern)

                # Open the file and extract URLs matching the pattern
                with open(file_path, 'r') as f:
                    for line in f:
                        url = line.strip()
                        match = regex.search(url)
                        if match:
                            code = match.group(1) or match.group(2)
                            _url_code_mapping.setdefault(code, []).append(url)

def get_urls(key):
    """
    Retrieve URLs corresponding to a given key from the cached mapping.

    Parameters:
    - key: The key to search for (string or integer).

    Returns:
    - A list of URLs associated with the key.
    """
    # Initialize the mapping if not already loaded
    if _url_code_mapping is None:
        _load_url_code_mapping()

    value = id_matches.get(str(key))
    if not value:
        return []

    # Retrieve URLs corresponding to the value
    return _url_code_mapping.get(value, [])