"""Weights configuration and functions for the ATLAS Open Magic REST API."""

# pylint: disable=line-too-long, too-many-locals

import logging
import os
from typing import Any, Optional

import requests
from tqdm import tqdm

from atlasopenmagic import metadata

PMG_WEIGHTS_API_URL = os.environ.get("PMG_WEIGHTS_API_URL", "https://atlas-pmg-api.app.cern.ch")

# Cache for weight metadata to avoid repeated API calls
_weight_metadata = {}
# Tell the metadata module to clear our cache whenever empty_metadata() is called
metadata.register_cache_clear_callback(lambda: _weight_metadata.clear())

_logger = logging.getLogger(__name__)


def get_weights(key: str, e_tag: Optional[str] = None) -> dict[str, Any]:
    """Retrieve weight metadata for a specific dataset in the current release.

    This function fetches the list of available weight names for a given dataset
    from the ATLAS Open Magic REST API. Weight metadata is useful for understanding
    what systematic variations and PDF sets are available for Monte Carlo datasets.

    Args:
        key: The dataset identifier (e.g., '306600').
        e_tag: An optional specific e_tag to query. If not provided, it will
               attempt to automatically resolve it from the dataset's metadata.

    Returns:
        A dictionary containing:
            - release_name: The name of the release
            - energy_level: The energy level (e.g., '13TeV', '13p6TeV')
            - dataset_number: The dataset number
            - weights: List of available weight names
            - weight_count: Number of available weights

    Raises:
        ValueError: If the dataset is not found or weights are not available.
        requests.exceptions.RequestException: If the API request fails.

    Example:
    ```python
    import atlasopenmagic as atom

    atom.set_release('2025r-evgen-13tev')
    weights = atom.get_weights('306600', e_tag='e8514')
    print("Found", weights['weight_count'], "weights")
    print(weights['weights'][:5])  # First 5 weight names
    ```
    """
    key_str = str(key).strip()
    cache_key = (
        f"{metadata.get_current_release()}:{key_str}:{e_tag}"
        if e_tag
        else f"{metadata.get_current_release()}:{key_str}"
    )

    # Check cache first
    if cache_key in _weight_metadata:
        _logger.debug("Returning cached weights for %s", key_str)
        return _weight_metadata[cache_key]

    _logger.info("Fetching weights for dataset %s in release %s", key_str, metadata.get_current_release())

    try:
        session = metadata.get_session()

        # We need to get the specific e_tag for the dataset if not optionally provided
        try:
            energy = metadata.get_metadata(key_str, "CoMEnergy")
            if not energy:
                energy = "13TeV"
            resolved_e_tag = e_tag or metadata.get_metadata(key_str, "e_tag")
        except Exception:
            resolved_e_tag = e_tag
            energy = "13TeV"

        if resolved_e_tag:
            url = f"{PMG_WEIGHTS_API_URL}/weights/dsid/{key_str}/tag/{resolved_e_tag}"
            response = session.get(url, timeout=30)
            response.raise_for_status()
            weight_list = response.json()
        else:
            url = f"{PMG_WEIGHTS_API_URL}/weights/dsid/{key_str}"
            response = session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            weights_dict = data.get("weights", {})
            # just take the first list if e_tag is not provided or not matched exactly
            weight_list = list(weights_dict.values())[0] if weights_dict else []

        weights_data = {
            "release_name": metadata.get_current_release(),
            "energy_level": energy,
            "dataset_number": key_str,
            "weights": weight_list,
            "weight_count": len(weight_list),
        }

        # Cache the result
        _weight_metadata[cache_key] = weights_data

        _logger.info("Found %d weights for dataset %s", len(weight_list), key_str)
        return weights_data

    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status == 404:
            raise ValueError(
                f"Weights not found for dataset '{key_str}' in release '{metadata.get_current_release()}'. "
                "Weight metadata may not be available for this dataset or release."
            ) from e
        raise e
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to fetch weights for dataset '{key_str}': {e}") from e


def get_weight_names(key: str, e_tag: Optional[str] = None) -> list[str]:
    """Retrieve just the list of weight names for a dataset.

    This is a convenience function that returns only the weight names,
    without the additional metadata.

    Args:
        key: The dataset identifier (e.g., '306600').
        e_tag: An optional specific e_tag to query.

    Returns:
        A list of weight names available for the dataset.

    Raises:
        ValueError: If the dataset is not found or weights are not available.

    Example:
    ```python
    import atlasopenmagic as atom

    atom.set_release('2025r-evgen-13tev')
    weight_names = atom.get_weight_names('306600', e_tag='e8514')
    print(weight_names[:3])  # First 3 weight names
    ```
    """
    weights_data = get_weights(key, e_tag=e_tag)
    return weights_data.get("weights", [])


def get_all_weights_for_release(release_name: Optional[str] = None) -> dict[str, list[str]]:
    """Retrieve all weight metadata for an entire release.

    This function fetches weight information for all datasets in a release.
    Note: This can be a large response depending on the release.

    Args:
        release_name: The name of the release. If None, uses the current release.

    Returns:
        A dictionary containing the release information and all datasets with their weights.

    Raises:
        ValueError: If the release is not found or weights are not available.
        requests.exceptions.RequestException: If the API request fails.

    Example:
    ```python
    import atlasopenmagic as atom

    all_weights = atom.get_all_weights_for_release('2025r-evgen-13tev')
    print("Datasets with weights:", len(all_weights['datasets']))
    ```
    """
    release = release_name or metadata.get_current_release()
    cache_key = f"release:{release}"

    # Check cache first
    if cache_key in _weight_metadata:
        _logger.debug("Returning cached weights for release %s", release)
        return _weight_metadata[cache_key]

    _logger.info("Fetching all weights for release %s", release)

    try:
        session = metadata.get_session()
        # Fallback implementation as PMG weight DB doesn't have a release-wide endpoint
        _logger.info("Retrieving all weights using bulk endpoint.")

        all_datasets = {}
        release_energy = "13TeV"  # default fallback

        # Collect datasets and their specific tags
        valid_datasets = []

        # Use the already cached metadata if we are querying the active release!
        # This completely avoids re-hammering the API server for datasets.
        if release == metadata.get_current_release():
            dataset_keys = metadata.available_datasets()
            for dsid in dataset_keys:
                try:
                    e_tag = metadata.get_metadata(dsid, "e_tag")
                    energy = metadata.get_metadata(dsid, "CoMEnergy")
                    if not energy:
                        energy = "13TeV"
                    if dsid:
                        valid_datasets.append({"dsid": int(dsid), "e_tag": e_tag, "energy": energy})
                except Exception:
                    continue
        else:
            # The weights should be always be fetched for the current release.
            _logger.error(
                "Release '%s' is not the current release. Unable to fetch dataset metadata.",
                release,
            )
            raise ValueError(
                f"Release '{release}' is not the current release. "
                f"Please use set_release('{release}') to switch to this release before fetching weights."
            )

        if valid_datasets:
            release_energy = valid_datasets[0]["energy"]

        total_ds = len(valid_datasets)
        chunk_size = 500  # Bulk API expects a max around 900 for SQLite

        pbar = (
            tqdm(total=total_ds, desc=f"Fetching weights for {release}", unit="datasets")
            if "tqdm" in globals()
            else None
        )

        try:
            for i in range(0, total_ds, chunk_size):
                chunk = valid_datasets[i : i + chunk_size]
                dsid_to_etag = {str(ds["dsid"]): ds["e_tag"] for ds in chunk}

                dsids_str = ",".join(str(ds["dsid"]) for ds in chunk)

                resp = session.get(
                    f"{PMG_WEIGHTS_API_URL}/weights/dsids/{dsids_str}",
                    timeout=120,
                )
                resp.raise_for_status()

                bulk_data = resp.json()

                for dsid_str, e_tags_weights in bulk_data.items():
                    expected_tag = dsid_to_etag.get(dsid_str)
                    # Specific e_tag found
                    if expected_tag and expected_tag in e_tags_weights:
                        all_datasets[dsid_str] = e_tags_weights[expected_tag]
                    # Otherwise fall back to whatever first tag we have
                    elif e_tags_weights:
                        all_datasets[dsid_str] = list(e_tags_weights.values())[0]

                if pbar:
                    pbar.update(len(chunk))
        finally:
            if pbar:
                pbar.close()

        result = {"release_name": release, "energy_level": release_energy, "datasets": all_datasets}

        if not all_datasets:
            raise ValueError(
                f"Weights not found for release '{release}'. Weights may not be available for this release."
            )

        # Cache the result
        _weight_metadata[cache_key] = result

        dataset_count = len(all_datasets)
        _logger.info("Found weights for %d datasets in release %s", dataset_count, release)
        return result

    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status == 404:
            raise ValueError(
                f"Weights not found for release '{release}'. "
                "Weight metadata may not be available for this release."
            ) from e
        raise e
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to fetch weights for release '{release}': {e}") from e
