"""ATLAS Open Data Magic Client.

This script provides a user-friendly Python client to interact with the ATLAS Open Magic REST API.
It simplifies the process of fetching metadata and file URLs for various datasets and releases
from the ATLAS Open Data project.

Example:
```
import atlasopenmagic as atom

# Set the desired release
atom.set_release('2025e-13tev-beta')

# Get metadata for a specific dataset
metadata = atom.get_metadata('301204')

# Get the file URLs for the 'exactly4lep' skim of that dataset
urls = atom.get_urls('301204', skim='exactly4lep')
print(urls)
```
"""


import os
import threading
import warnings

# Some functions (like metadata) can return any type
from typing import Any, Optional

import requests

# --- Global Configuration & State ---


# The active release can be set via the 'ATLAS_RELEASE' environment variable.
# Defaults to '2024r-pp' if the variable is not set.
current_release = os.environ.get("ATLAS_RELEASE", "2024r-pp")


# The API endpoint can be set via the 'ATLAS_API_BASE_URL' environment variable.
# This allows pointing the client to different API instances (e.g.,
# development, production).
API_BASE_URL = os.environ.get(
    "ATLAS_API_BASE_URL", "https://atlasopenmagic-rest-api-atlas-open-data.app.cern.ch"
)


# The local cache to store metadata fetched from the API for the current release.
# This dictionary is populated on the first call to get_metadata() for a
# new release.
_metadata = {}


# A thread lock to ensure that the cache is accessed and modified safely
# in multi-threaded environments.
_metadata_lock = threading.Lock()


# The local path for caching dataset files, if set.
current_local_path = None


# A user-friendly dictionary describing the available data releases.
RELEASES_DESC = {
    "2016e-8tev": (
        "2016 Open Data for education release of 8 TeV proton-proton collisions "
        "(https://opendata.cern.ch/record/3860)."
    ),
    "2020e-13tev": (
        "2020 Open Data for education release of 13 TeV proton-proton collisions " "(https://cern.ch/2r7xt)."
    ),
    "2024r-pp": (
        "2024 Open Data for research release for proton-proton collisions "
        "(https://opendata.cern.record/80020)."
    ),
    "2024r-hi": (
        "2024 Open Data for research release for heavy-ion collisions "
        "(https://opendata.cern.ch/record/80035)."
    ),
    "2025e-13tev-beta": (
        "2025 Open Data for education and outreach beta release for 13 TeV proton-proton collisions "
        "(https://opendata.cern.ch/record/93910)."
    ),
    "2025r-evgen-13tev": (
        "2025 Open Data for research release for event generation at 13 TeV "
        "(https://opendata.cern.ch/record/160000)."
    ),
    "2025r-evgen-13p6tev": (
        "2025 Open Data for research release for event generation at 13.6 TeV "
        "(https://opendata.cern.ch/record/160000)."
    ),
}


AVAILABLE_FIELDS = [
    "dataset_number",
    "physics_short",
    "e_tag",
    "cross_section_pb",
    "genFiltEff",
    "kFactor",
    "nEvents",
    "sumOfWeights",
    "sumOfWeightsSquared",
    "process",
    "generator",
    "keywords",
    "file_list",
    "description",
    "job_path",
    "CoMEnergy",
    "GenEvents",
    "GenTune",
    "PDF",
    "Release",
    "Filters",
    "release.name",
    "skims",
]


# --- Internal Helper Functions ---


def _apply_protocol(url: str, protocol: str) -> str:
    """Internal helper to transform a root URL into the specified protocol format.

    Args:
        url: The base 'root://' URL.
        protocol: The target protocol ('https', 'eos', or 'root').

    Returns:
        The transformed URL.

    Raises:
        ValueError: If protocol is not one of 'root', 'https', or 'eos'.
    """
    if protocol == "https":
        # Convert to a web-accessible URL via opendata.cern.ch
        return url.replace("root://eospublic.cern.ch:1094/", "https://opendata.cern.ch")
    if protocol == "eos":
        # Provide the path relative to the EOS mount point
        return url.replace("root://eospublic.cern.ch:1094/", "")
    if protocol == "root":
        # Return the original URL for direct ROOT access
        return url
    raise ValueError(f"Invalid protocol '{protocol}'. Must be 'root', 'https', or 'eos'.")


def _fetch_and_cache_release_data(release_name: str) -> str:
    """Internal helper to fetch all datasets for a release and populate the local cache.

    This function uses the paginated `/datasets?release_name=...&skip=...&limit=...`
    API endpoint to efficiently retrieve datasets in manageable batches, preventing
    memory and network issues that arise from very large releases.

    Args:
        release_name: The name of the release to fetch.

    Raises:
        requests.exceptions.RequestException: If the API call fails or returns an error.
    """
    global _metadata, AVAILABLE_FIELDS
    print(f"Fetching and caching all metadata for release: {release_name}...")

    page_size = 3000  # The number of datasets to fetch per API call, see https://github.com/atlas-outreach-data-tools/atlasopenmagic/pull/63
    skip = 0  # Offset for pagination; incremented by page_size at each iteration
    total_fetched = 0  # Counter to keep track of how many datasets have been cached
    new_cache = {}  # Temporary cache for atomic update once all data is fetched
    looper = 0  # Safety counter to prevent infinite loops

    try:
        while True:
            looper += 1
            if looper > 5:  # We do not expect to have more than 15000 datasets for now.
                raise RuntimeError("Exceeded maximum number of pagination loops (5). Aborting fetch.")
            response = requests.get(
                f"{API_BASE_URL}/datasets",
                params={"release_name": release_name, "skip": skip, "limit": page_size},
                timeout=100,
            )
            response.raise_for_status()  # Raise for any HTTP error codes (4xx, 5xx)
            datasets_page = response.json()
            if not datasets_page:
                break
            # Now each dataset should be a dict
            for dataset in datasets_page:
                ds_number_str = str(dataset["dataset_number"])
                new_cache[ds_number_str] = dataset
                # Also cache by the physics short name, if available, for user convenience.
                if dataset.get("physics_short"):
                    new_cache[dataset["physics_short"].lower()] = dataset

            num_this_page = len(datasets_page)
            total_fetched += num_this_page
            print(f"Fetched {total_fetched} datasets so far...")
            # Advance the skip marker for the next page.
            skip += page_size

    except requests.exceptions.RequestException as e:
        # Handle errors, timeouts, etc., and propagate the error up.
        raise requests.exceptions.RequestException(
            f"Failed to fetch metadata for release '{release_name}' from API: {e}"
        ) from e
    except RuntimeError as e:
        raise RuntimeError(f"Failed to fetch metadata for release '{release_name}': {e}") from e

    # Atomically replace the global cache with the newly populated one.
    _metadata = new_cache
    # Update available fields - get what's really there
    AVAILABLE_FIELDS = []
    for k in _metadata:
        AVAILABLE_FIELDS += [m for m in _metadata[k] if m not in AVAILABLE_FIELDS]
    # Tell the users that we're done
    print(f"Successfully cached {total_fetched} datasets.")


# --- Public API Functions ---


def available_releases() -> dict[str, tuple[str]]:
    """Display a list of all available data releases and their descriptions.

    This function prints directly to the console for easy inspection with clean, aligned formatting.

    Returns:
        A dictionary mapping release names to their description tuples.
    """
    # Find the length of the longest release name to calculate padding.
    max_len = max(len(k) for k in RELEASES_DESC.keys())

    print("Available releases:")
    print("========================================")
    # Use ljust() to pad each release name to the max length for perfect
    # alignment.
    for release, desc in RELEASES_DESC.items():
        print(f"{release.ljust(max_len)}  {desc}")
    return RELEASES_DESC


def get_current_release() -> str:
    """Return the name of the currently active data release.

    Returns:
        The name of the current release (e.g., '2024r-pp').
    """
    return current_release


def _convert_to_local(url: str, current_local_path: Optional[str] = None) -> str:
    """Convert to a local file path if one is set for the current release.

    Args:
        url: The URL to convert.
        current_local_path: The current local path setting.

    Returns:
        The converted local path or original URL if no local path is set.
    """
    if not current_local_path:
        return url  # No local mode active
    if url.startswith(current_local_path):
        return url  # Already local
    # remove protocol and hostname, keep relative EOS path:
    if current_local_path == "eos":
        # Special case for EOS: just return the path
        return os.path.join("/eos/", url.split("eos/", 1)[-1])

    rel = url.split(
        "/",
    )[-1]
    return os.path.join(current_local_path, rel)


def set_release(release: str, local_path: Optional[str] = None) -> None:
    """Set the active data release for all subsequent API calls.

    Changing the release will clear the local metadata cache, forcing a re-fetch
    of data from the API upon the next request.

    Args:
        release: The name of the release to set as active.
        local_path: A local directory path to use for caching dataset files.
            If provided, the client will assume that datasets are available locally
            at this path. Provide "eos" as the local_path to access using the native POSIX.

    Raises:
        ValueError: If the provided release name is not valid.
    """
    global current_release, _metadata, current_local_path
    if release not in RELEASES_DESC:
        raise ValueError(f"Invalid release '{release}'. Use one of: {', '.join(RELEASES_DESC)}")

    with _metadata_lock:
        current_release = release
        if local_path:
            # Check if the local path exists
            if not os.path.isdir(local_path) and local_path != "eos":
                warnings.warn(
                    f"Local path '{local_path}' does not exist - you may create or rsync later.",
                    UserWarning,
                    stacklevel=2,
                )
            current_local_path = local_path  # Set the local path for this release
        else:
            current_local_path = None  # disable local path

        _metadata = {}  # Invalidate and clear the cache
        # Fetch the data for the updated release and load it into the cache
        _fetch_and_cache_release_data(current_release)

    print(
        f"Active release: {current_release}. "
        f"(Datasets path: {current_local_path if current_local_path else 'REMOTE'})"
    )


def find_all_files(local_path: str, warnmissing: bool = False) -> None:
    """Replace cached remote URLs with corresponding local file paths if files exist locally.

    This function only affects the currently active release, and requires `_metadata`
    to be populated (it will trigger a fetch automatically).

    Workflow:
        1. Walk the given `local_path` once and build a lookup dictionary of available files.
           The lookup is keyed only by filename (basename), so this assumes filenames are unique.
        2. For every dataset in the current release cache:
           - Replace each file URL with its local path if the corresponding file exists locally.
           - For files missing locally, keep the remote URL and optionally emit a warning.
        3. This is done both for the main `file_list` and for each skim's `file_list`.

    Args:
        local_path: Root directory of your local dataset copy. Can have any internal subdirectory
            structure; only filenames are used for matching.
        warnmissing: If True, issue a `UserWarning` for every file that is in metadata but
            not found locally.

    Note:
        - Matching is based on filename only, not relative EOS path.
        - If you have multiple files with the same name in different datasets,
          the first one found in `os.walk()` will be used for replacement.
        - This modifies `_metadata` in place for the current session.
        - After running this, any `get_urls()` call will return local paths
          where available, otherwise the original remote URLs.
    """
    # Ensure metadata is loaded for the current release
    _fetch_and_cache_release_data(current_release)

    abs_local = os.path.abspath(local_path)

    # Build an index of all available local files for quick O(1) lookups
    local_index = {}
    for dirpath, _, filenames in os.walk(abs_local, followlinks=True):
        for fname in filenames:
            local_index[fname] = os.path.join(dirpath, fname)

    # Track which datasets were updated and how many files were replaced
    updated_samples = []
    replaced_file_count = 0

    # Only process main dataset entries (exclude physics_short aliases)
    filtered_metadata = {k: v for k, v in _metadata.items() if k.isdigit() or k == "data"}

    for sample, md in filtered_metadata.items():
        # Main file_list
        if "file_list" in md:
            new_list = []
            for url in md["file_list"]:
                fname = os.path.basename(url)
                if fname in local_index:
                    new_list.append(local_index[fname])
                    updated_samples.append(sample)
                    replaced_file_count += 1
                else:
                    if warnmissing:
                        warnings.warn(
                            f"File '{fname}' for '{sample}' not found in '{local_path}'.",
                            UserWarning,
                            stacklevel=2,
                        )
                    new_list.append(url)  # Keep remote if missing locally
            md["file_list"] = new_list

        # Skim file_lists
        for skim in md.get("skims", []):
            new_list = []
            for url in skim["file_list"]:
                fname = os.path.basename(url)
                if fname in local_index:
                    new_list.append(local_index[fname])
                    updated_samples.append(sample)
                    replaced_file_count += 1
                else:
                    if warnmissing:
                        warnings.warn(
                            f"Skim file '{fname}' for '{sample}' not found in '{local_path}'.",
                            UserWarning,
                            stacklevel=2,
                        )
                    new_list.append(url)
            skim["file_list"] = new_list

    # Summary reporting
    updated_samples = sorted(set(updated_samples))
    total_files_in_updated_samples = sum(
        len(_metadata[sample]["file_list"]) if sample in _metadata else 0 for sample in updated_samples
    )

    print(
        f"Metadata updated with local paths for {len(updated_samples)} samples "
        f"({updated_samples}) and {replaced_file_count} files "
        f"(out of {total_files_in_updated_samples} in those samples)."
    )


def get_all_info(key: str, var: Optional[str] = None) -> Any:
    """Retrieve all the information for a given dataset.

    If the cache is empty for the current release, this function will trigger a fetch
    from the API to populate it.

    Args:
        key: The dataset identifier (e.g., '301204').
        var: A specific metadata field to retrieve.
            If None, the entire metadata dictionary is returned.
            Supports old and new field names.

    Returns:
        The full info dictionary for the dataset, or the value of the single field
        if 'var' was specified.

    Raises:
        ValueError: If the dataset key or the specified variable field is not found.
    """
    global _metadata
    key_str = str(key).strip().lower()  # Normalize the key to a string for consistency

    with _metadata_lock:
        # Fetch-on-demand: If the cache is empty, populate it.
        if not _metadata:
            _fetch_and_cache_release_data(current_release)

    # Retrieve the full dataset dictionary from the cache.
    sample_data = _metadata.get(key_str)

    if not sample_data:
        raise ValueError(
            f"Invalid key: '{key_str}'. \
            No dataset found with this ID or name in release '{current_release}'."
        )

    # If no specific variable is requested, return almost the whole dictionary.
    if not var:
        return sample_data

    # If a specific variable is requested, try to find it.
    # 1. Check for a direct match with the new API field names.
    if var in sample_data:
        return sample_data.get(var)

    raise ValueError(
        f"Invalid field name: '{var}'. Available fields: {', '.join(sorted(set(AVAILABLE_FIELDS)))}"
    )


def get_metadata(key: str, var: Optional[str] = None) -> Any:
    """Retrieve the metadata (no file lists) for a given dataset.

    Dataset is identified by its number or physics short name.
    If the cache is empty for the current release, this function will trigger a fetch
    from the API to populate it.

    Args:
        key: The dataset identifier (e.g., '301204').
        var: A specific metadata field to retrieve. If None, the entire
            metadata dictionary is returned. Supports old and new field names.

    Returns:
        The full metadata dictionary for the dataset, or the value of the
        single field if 'var' was specified.

    Raises:
        ValueError: If the dataset key or the specified variable field is not found.
    """
    all_info = get_all_info(key, var)
    if var is None:
        return {x: all_info[x] for x in all_info if x not in ["skims", "file_list"]}
    return all_info


def get_metadata_fields() -> list[str]:
    """Retrieve the list of available metadata fields.

    Returns:
        A sorted list of available metadata fields.
    """
    return sorted(AVAILABLE_FIELDS)


def get_urls(key: str, skim: str = "noskim", protocol: str = "root", cache: Optional[bool] = None) -> list[str]:
    """Retrieve file URLs for a given dataset, with options for skims and protocols.

    This function correctly interprets the structured skim data from the API.

    Args:
        key: The dataset identifier.
        skim: The desired skim type. Defaults to 'noskim' for the base,
            unfiltered dataset. Other examples: 'exactly4lep', '3lep'.
        protocol: The desired URL protocol. Can be 'root', 'https', or 'eos'.
            Defaults to 'root'.
        cache: Use the simplecache mechanism of fsspec to locally cache
            files instead of streaming them. Default True for https,
            False for root protocol.

    Returns:
        A list of file URLs matching the criteria.

    Raises:
        ValueError: If the requested skim or protocol is not available for the dataset.
    """
    # First, get the complete metadata for the dataset.
    dataset = get_all_info(key)

    # Now, build a dictionary of all available file lists from the structured
    # API response.
    available_files = {}

    # The 'file_list' at the top level corresponds to the 'noskim' version.
    if dataset.get("file_list"):
        available_files["noskim"] = dataset["file_list"]

    # The 'skims' list contains objects, each with their own 'skim_type' and
    # 'file_list'.
    for skim_obj in dataset.get("skims", []):
        available_files[skim_obj["skim_type"]] = skim_obj["file_list"]

    # Check if the user-requested skim exists in our constructed dictionary.
    if skim not in available_files:
        available_skims = ", ".join(sorted(available_files.keys()))
        if available_skims == "noskim":
            raise ValueError(
                f"Dataset '{key}' only has the base (unskimmed) version available.\n \
                Are you sure that this release ({current_release}) has skimmed datasets?"
            )
        raise ValueError(f"Skim '{skim}' not found for dataset '{key}'. Available skims: {available_skims}")

    # Retrieve the correct list of URLs and apply the requested protocol
    # transformation.
    raw_urls = available_files[skim]

    # Apply protocol transformation first
    urls = [_apply_protocol(u, protocol.lower()) for u in raw_urls]

    # Convert to local paths if configured for the current release
    if current_local_path:
        # Convert the URLs to local paths if a local path is set
        urls = [_convert_to_local(u, current_local_path) for u in urls]

    # If caching is requested, add it to the paths we return
    # Note: Don't add cache prefix to local file paths
    cache_str = "simplecache::" if cache or (cache is None and protocol == "https") else ""
    final_urls = []
    for u in urls:
        if current_local_path and "://" not in u:
            final_urls.append(u)  # Local path: no caching prefix
        else:
            final_urls.append(cache_str + u)
    return final_urls


def available_datasets() -> list[str]:
    """Return a sorted list of all available dataset numbers for the current release.

    Returns:
        A sorted list of dataset numbers as strings.
    """
    with _metadata_lock:
        # Ensure the cache is populated before reading from it.
        if not _metadata:
            _fetch_and_cache_release_data(current_release)
    # The cache contains keys for both dataset numbers and physics short names.
    # We filter to return only the numeric dataset IDs.
    return sorted([k for k in _metadata if k.isdigit() or k == "data"])


def available_skims() -> list[str]:
    """Returns a sorted list of skims available for the current release.

    Skims are pre-selected subsets of events that share some common
    characteristic, like having two muons. Processing a skim can save
    considerable time compared to processing the entire dataset (noskim),
    and the result is the same as long as the selection used in the
    analysis is more restrictive than the selection used to create the
    skim.

    Returns:
        A sorted list of skims available for the current release.
    """
    with _metadata_lock:
        # Ensure the cache is populated before reading from it.
        if not _metadata:
            _fetch_and_cache_release_data(current_release)
    # Roll through the datasets and get the unique skims
    skim_list = []
    for _, metadata in _metadata.items():
        if "skims" in metadata and metadata["skims"] is not None:
            # This should be a little less memory hungry than a giant merge and then list-set-list
            skim_list += [x["skim_type"] for x in metadata["skims"] if x["skim_type"] not in skim_list]
    # Return the sorted list
    return sorted(skim_list)


def get_all_metadata() -> dict[str, dict]:
    """Return the entire metadata dictionary, en mass.

    Returns:
        The metadata dictionary.
    """
    with _metadata_lock:
        # Ensure the cache is populated before reading from it.
        if not _metadata:
            _fetch_and_cache_release_data(current_release)
    return _metadata


def empty_metadata() -> None:
    """Internal helper function to empty the metadata cache and leave it empty."""
    # Make sure we work with the global object
    global _metadata, AVAILABLE_FIELDS
    # Clear the cache
    with _metadata_lock:
        _metadata = {}
    # No more metadata fields available
    AVAILABLE_FIELDS = []


# --- Metadata search functions


def available_keywords() -> list[str]:
    """Return a sorted list of available keywords in use in the current release.

    Returns:
        A sorted list of keywords as strings.
    """
    with _metadata_lock:
        # Ensure the cache is populated before reading from it.
        if not _metadata:
            _fetch_and_cache_release_data(current_release)
    # Roll through the keywords and get the unique ones
    keyword_list = []
    for _, metadata in _metadata.items():
        if "keywords" in metadata and metadata["keywords"] is not None:
            # This should be a little less memory hungry than a giant merge and then list-set-list
            keyword_list += [keyword for keyword in metadata["keywords"] if keyword not in keyword_list]
    # Return the sorted list
    return sorted(keyword_list)


def match_metadata(field: str, value: Any, float_tolerance: float = 0.01) -> list[tuple[str, str]]:
    """Return a sorted list of datasets with metadata field matching value.

    Args:
        field: The metadata field to search.
        value: The value to search for.
        float_tolerance: The fractional tolerance for floating point number matches.

    Returns:
        A sorted list of matching datasets as tuples of (dataset_id, physics_short).

    Raises:
        ValueError in case the requested field is not known
    """
    with _metadata_lock:
        # Ensure the cache is populated before reading from it.
        if not _metadata:
            _fetch_and_cache_release_data(current_release)
    # Now check if our field is available
    if field not in AVAILABLE_FIELDS:
        raise ValueError(
            f"Invalid field name: '{field}'. Available fields: {', '.join(sorted(set(AVAILABLE_FIELDS)))}"
        )

    # Go through all the datasets and look for matches
    matches = []
    for k, metadata in _metadata.items():
        # Keep only the pure numeric (DSID) results for clarity
        if not k.isdigit():
            continue
        # Now do the searching
        if field in metadata and metadata[field] is not None:
            # For strings allow matches of substrings and items in the lists
            if isinstance(metadata[field], (str, list)):
                if value is not None and value in metadata[field]:
                    matches += [k]
            # For numbers that aren't zero, match within tolerance
            elif isinstance(metadata[field], float) and value is not None and float(value) != 0:
                if abs(float(value) - metadata[field]) / float(value) < float_tolerance:
                    matches += [k]
            # For other field types require an exact match
            elif value == metadata[field]:
                matches += [k]
        # Allow people to search for empty metadata fields
        elif (field not in metadata or metadata[field] is None) and value is None:
            matches += [k]
    # Now, because context helps, let's make this into a list of pairs
    matches = [(x, _metadata[x]["physics_short"]) for x in matches]

    # Tell the users explicitly in case there are no matches
    if len(matches) == 0:
        print("No datasets found.")
    return sorted(matches)


# --- Metadata saving and loading functions ---


def save_metadata(file_name: str = "metadata.json") -> None:
    """Save the metadata in an output file.

    Attempts to adjust the output based on the file extension, currently supporting txt and json.
    Loads the metadata if it is currently empty.

    Args:
        file_name: The name of the file to save the metadata to, with full path and extension.

    Raises:
        ValueError: If the requested file type is not supported.
    """
    # Check if metadata is already loaded, load it if needed
    with _metadata_lock:
        # Ensure the cache is populated before reading from it.
        if not _metadata:
            _fetch_and_cache_release_data(current_release)

    # If they request json file saving, we have a very easy time
    if file_name.endswith(".json"):
        import json

        with open(file_name, "w") as outfile:
            json.dump(
                _metadata,
                outfile,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ": "),
            )
    # If they want text files, just use pretty print
    elif file_name.endswith(".txt"):
        import pprint

        with open(file_name, "w") as outfile:
            pprint.pprint(_metadata, outfile, indent=2)
    # No other formats supported at this time
    else:
        raise ValueError(
            f'Requested metadata saving to unsupported filetype: {file_name.split(".")[-1]}.'
            f"Currently supporting txt and json."
        )


def read_metadata(file_name: str = "metadata.json", release: str = "custom") -> None:
    """Read the metadata from an input file.

    Overwrites existing metadata.

    Args:
        file_name: The name of the file to load the metadata from, with full path.
        release: The name of the release for this metadata; default 'custom'.

    Raises:
        ValueError: If the loaded data is not a dictionary as expected.
    """
    # Grab the global _metadata object and current release so that we can adjust them
    global _metadata, current_release, AVAILABLE_FIELDS

    # Let the users know that we heard them
    print(f"Loading metadata from {file_name}, and setting release to {release}")

    # Lock it up so that no one else is writing to it at the moment
    with _metadata_lock:
        # Now load the metadata. We'll take it all, directly, just like we saved it above
        import json

        with open(file_name) as input_metadata:
            my_metadata = json.load(input_metadata)
            if not isinstance(my_metadata, dict):
                raise ValueError(f"Did not get expected dictionary from {file_name}. Will not load metadata.")
            _metadata = my_metadata

        # Now set the release if all went according to plan
        current_release = release

        # And update our available fields
        AVAILABLE_FIELDS = []
        for k in _metadata:
            AVAILABLE_FIELDS += [m for m in _metadata[k] if m not in AVAILABLE_FIELDS]


# --- Deprecated Functions (for backward compatibility) ---


def get_urls_data(key: str, protocol: str = "root") -> list[str]:
    """Retrieve file URLs for the base (unskimmed) dataset.

    Note:
        DEPRECATED: Please use get_urls(key, skim='noskim', protocol=protocol, cache=cache) instead.

    Args:
        key: The dataset identifier.
        protocol: The desired URL protocol.

    Returns:
        A list of file URLs for the dataset.
    """
    warnings.warn(
        "get_urls_data() is deprecated. Please use get_urls() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_urls("data", skim=key, protocol=protocol)
