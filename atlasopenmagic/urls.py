import os
import re
import threading
from atlasopenmagic.data.id_matches import id_matches

# Global variables for caching URLs
_url_code_mapping = None
_mapping_lock = threading.Lock()

# File paths configuration
FILE_PATHS = {
    "standard": os.path.join(os.path.dirname(__file__), 'data', 'urls.txt'),
    "tev8": os.path.join(os.path.dirname(__file__), 'data', 'urls_TeV8.txt'),
}

# Regex patterns configuration
REGEX_PATTERNS = {
    "standard": r'DAOD_PHYSLITE\.(\d+)\.',
    "tev8": r'(?:mc_(\d+)|Data(\d+))',
}

def load_url_code_mapping(file_path, regex_pattern):
    """
    Load URLs from a file and build a mapping from extracted codes to URLs.

    Parameters:
    - file_path: Path to the file containing URLs.
    - regex_pattern: Regex pattern to extract codes from URLs.

    Returns:
    - A dictionary mapping extracted codes to lists of URLs.
    """
    with _mapping_lock:
        mapping = {}
        regex = re.compile(regex_pattern)

        with open(file_path, 'r') as f:
            for line in f:
                url = line.strip()
                match = regex.search(url)
                if match:
                    # Check which group matched
                    code = match.group(1) or match.group(2)
                    mapping.setdefault(code, []).append(url)

        return mapping

def build_mappings():
    """
    Build mappings for all configured file paths and regex patterns.

    Returns:
    - A dictionary combining all mappings from different configurations.

    Raises:
    - ValueError: If FILE_PATHS and REGEX_PATTERNS are not of the same size.
    """
    if len(FILE_PATHS) != len(REGEX_PATTERNS):
        raise ValueError("FILE_PATHS and REGEX_PATTERNS must be the same size.")

    combined_mapping = {}

    for key, file_path in FILE_PATHS.items():
        if key in REGEX_PATTERNS:
            combined_mapping.update(load_url_code_mapping(file_path, REGEX_PATTERNS[key]))
        else:
            raise KeyError(f"Key '{key}' in FILE_PATHS is not present in REGEX_PATTERNS.")

    return combined_mapping

def initialize_mappings():
    """
    Initialize URL mappings in a thread-safe manner.
    """
    global _url_code_mapping
    if _url_code_mapping is not None:
        return

    with _mapping_lock:
        if _url_code_mapping is None:  # Double-checked locking
            _url_code_mapping = build_mappings()

def get_urls(key):
    """
    Retrieve URLs corresponding to a given key.

    Parameters:
    - key: The key to search for (string or integer).

    Returns:
    - A list of URLs associated with the key.
    """
    if _url_code_mapping is None:
        initialize_mappings()

    value = id_matches.get(str(key))
    if not value:
        return []

    return _url_code_mapping.get(value, [])