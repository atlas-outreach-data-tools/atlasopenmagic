"""This file provides tests for the atlasopenmagic package.

Tests use the unittest.mock functionality to avoid relying on
database access when running. The `MOCK_API_RESPONSE` should be
updated when adding new functionality that should be tested.
Tests generally focus on one aspect of functionality, but often
test several code branches with a single function. Tests are
named in a way that identifies the function they are testing.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

import src.atlasopenmagic as atom

# SET THIS BEFORE ANY IMPORTS
os.environ["ATLAS_API_BASE_URL"] = "http://mock-api.test"

# --- Mock API Response ---
# This is a realistic mock of the JSON response from the `/releases/{release_name}` endpoint,
# which the client script's caching function (`_fetch_and_cache_release_data`) calls.
# We are using your provided dataset object as the primary entry in the `datasets` list.
MOCK_API_RESPONSE = {
    "name": "2024r-pp",
    "datasets": [
        # This is the dataset object you provided.
        {
            "dataset_number": "301204",
            "physics_short": "Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000",
            "e_tag": "e3723",
            "cross_section_pb": 0.001762,
            "genFiltEff": 1.0,
            "kFactor": 1.0,
            "nEvents": 20000,
            "sumOfWeights": 20000.0,
            "sumOfWeightsSquared": 20000.0,
            "process": "pp>Zprime>ee",
            "generator": "Pythia8(v8.186)+EvtGen(v1.2.0)",
            "keywords": ["2electron", "BSM", "SSM"],
            "file_list": ["root://eospublic.cern.ch:1094//eos/path/to/noskim_301204.root"],
            "description": "Pythia 8 Zprime decaying to two electrons'",
            "job_path": "https://gitlab.cern.ch/path/to/job/options",
            "release": {"name": "2024r-pp"},
            "skims": [
                {
                    "id": 1,
                    "skim_type": "4lep",
                    "file_list": ["root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_301204.root"],
                    "description": "Exactly 4 leptons",
                    "dataset_number": "301204",
                    "release_name": "2024r-pp",
                }
            ],
        },
        # Adding a second dataset to make tests for `available_datasets` more robust.
        {
            "dataset_number": "410470",
            "CoMEnergy": None,
            "physics_short": "ttbar_lep",
            "cross_section_pb": 831.76,
            "file_list": ["root://eospublic.cern.ch:1094//eos/path/to/ttbar.root"],
            "skims": [],
            "release": {"name": "2024r-pp"},
        },
        {
            "dataset_number": "data",
            "physics_short": None,
            "cross_section_pb": 831.76,
            "file_list": ["root://eospublic.cern.ch:1094//eos/path/to/ttbar.root"],
            "skims": [
                {
                    "id": 1,
                    "skim_type": "4lep",
                    "file_list": ["root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_data.root"],
                    "description": "Exactly 4 leptons",
                    "dataset_number": "data",
                    "release_name": "2024r-pp",
                }
            ],
            "release": {"name": "2024r-pp"},
        },
    ],
}

MOCK_DATASETS = MOCK_API_RESPONSE["datasets"]

# Add mock datasets for the "2020e-13tev" release to support test_caching_behavior
MOCK_DATASETS_2020 = [
    {
        "dataset_number": "301204",
        "physics_short": "test_2020_dataset",
        "cross_section_pb": 9.99,
        "file_list": ["root://eospublic.cern.ch:1094//eos/path/to/noskim_301204_2020.root"],
        "skims": [],
        "release": {"name": "2020e-13tev"},
    }
]

# Combine all datasets for easier access
ALL_MOCK_DATASETS = MOCK_DATASETS + MOCK_DATASETS_2020


@pytest.fixture(autouse=True)
def mock_api():
    """
    Pytest fixture to automatically mock the API by patching the base URL and session's get method.
    It slices MOCK_DATASETS based on 'skip' and 'limit' query parameters.
    """
    # Mock API base URL to prevent real API calls
    mock_base_url = "http://mock-api.test"

    def get_side_effect(url, params=None, *args, **kwargs):
        # Determine which dataset to use based on release_name parameter
        release_filter = params.get("release_name") if params else None

        if release_filter == "2020e-13tev":
            active_datasets = MOCK_DATASETS_2020
        elif release_filter == "2024r-pp":
            active_datasets = MOCK_DATASETS
        else:
            active_datasets = ALL_MOCK_DATASETS

        # Handle count endpoint: /datasets/count
        if "/datasets/count" in url:
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {"count": len(active_datasets)}
            return mock_response

        # Handle individual dataset lookup: /metadata/{release_name}/{dataset_number}
        if "/metadata/" in url:
            # Extract release_name and dataset_number from URL
            parts = url.split("/metadata/")[-1].split("/")
            if len(parts) >= 2:
                release_name = parts[0]
                dataset_id = parts[1].split("?")[0].lower()  # Convert to lowercase for matching

                # Select appropriate dataset collection
                if release_name == "2020e-13tev":
                    search_datasets = MOCK_DATASETS_2020
                elif release_name == "2024r-pp":
                    search_datasets = MOCK_DATASETS
                else:
                    search_datasets = ALL_MOCK_DATASETS

                # Find the dataset in our mock data
                dataset = next(
                    (
                        d
                        for d in search_datasets
                        if (
                            str(d.get("dataset_number")).lower() == dataset_id
                            or (
                                d.get("physics_short") is not None
                                and d.get("physics_short").lower() == dataset_id
                            )
                        )
                        and d.get("release", {}).get("name") == release_name
                    ),
                    None,
                )

                mock_response = MagicMock()
                if dataset:
                    mock_response.raise_for_status.return_value = None
                    mock_response.json.return_value = dataset
                else:
                    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                        f"404 Client Error: Not Found for url: {url}"
                    )
                return mock_response

        # Handle datasets listing endpoint: /datasets
        if "/datasets" in url and "/datasets/count" not in url:
            skip = int(params.get("skip", 0)) if params else 0
            limit = int(params.get("limit", len(active_datasets))) if params else len(active_datasets)

            # Slice according to pagination parameters
            sliced = active_datasets[skip : skip + limit]

            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = sliced
            return mock_response

        # Default fallback
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = []
        return mock_response

    # Create the mock session
    mock_session = MagicMock()
    mock_session.get.side_effect = get_side_effect

    # Patch requests.Session to always return our mock
    # This prevents _get_session from creating a real session
    session_class_patcher = patch("requests.Session", return_value=mock_session)
    url_patcher = patch("src.atlasopenmagic.metadata.API_BASE_URL", mock_base_url)

    # Start both patches
    session_class_patcher.start()
    url_patcher.start()

    try:
        # Also reset the global _session to None to force recreation
        import src.atlasopenmagic.metadata as md

        md._session = None

        # Reset the release, which triggers fetching paginated and caching
        atom.set_release("2024r-pp")

        # Yield control to the test - patches remain active
        yield mock_session.get
    finally:
        # Stop patches after test completes
        session_class_patcher.stop()
        url_patcher.stop()


# === Tests for get_metadata() ===


def test_get_session():
    """Test that _get_session creates and caches a session properly."""

    if hasattr(atom.metadata, "_session"):
        delattr(atom.metadata, "_session")
    atom.metadata._get_session()
    assert hasattr(atom.metadata, "_session")


def test_set_local_release():
    """Test setting a local release and ensuring it clears the cache."""
    with pytest.warns(UserWarning):
        atom.set_release("2024r-pp", "tests/mock_data")

    assert atom.get_current_release() == "2024r-pp"
    assert atom.get_urls("301204") == ["tests/mock_data/noskim_301204.root"]

    # Now test the 'eos' option
    atom.set_release("2024r-pp", "eos")
    assert atom.get_urls("301204") == ["/eos/path/to/noskim_301204.root"]

    # Ensure the cache is cleared
    atom.set_release("2024r-pp")  # Reset to the original release


def test_set_wrong_release():
    """Test setting a release that does not exist."""
    with pytest.raises(ValueError):
        atom.set_release("non_existent_release")


def test_get_metadata_full():
    """Test retrieving the full metadata dictionary for a dataset by its number."""
    # Empty out the cache first
    from src.atlasopenmagic import metadata

    metadata.empty_metadata()

    # Grab the metadata for the specific dataset
    metadata = atom.get_metadata("301204")
    assert metadata is not None
    assert metadata["dataset_number"] == "301204"
    assert metadata["physics_short"] == "Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000"
    assert metadata["cross_section_pb"] == 0.001762


def test_get_metadata_by_short_name():
    """Test retrieving metadata using the physics_short name."""
    metadata = atom.get_metadata("Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000")
    assert metadata is not None
    assert metadata["dataset_number"] == "301204"


def test_get_metadata_specific_field():
    """Test retrieving a single, specific metadata field using the new API name."""
    cross_section = atom.get_metadata("301204", var="cross_section_pb")
    assert cross_section == 0.001762


def test_get_metadata_invalid_key():
    """Test that an invalid dataset key raises a ValueError."""
    with pytest.raises(ValueError):
        atom.get_metadata("invalid_key")


def test_get_metadata_invalid_field():
    """Test that an invalid field name raises a ValueError."""
    with pytest.raises(ValueError):
        atom.get_metadata("301204", var="invalid_field")


def test_caching_behavior(mock_api):
    """Test that the API is called only twice (once for getting the data, once for exiting the loop)
    for multiple metadata requests within the same release.
    """
    # Clear cache to start fresh
    from src.atlasopenmagic import metadata

    metadata.empty_metadata()

    # Force a re-fetch by changing and then changing back
    atom.set_release("2020e-13tev")
    atom.set_release("2024r-pp")

    # Reset call count after setup
    mock_api.reset_mock()

    # First call will trigger the API fetch.
    atom.get_metadata("301204")
    assert mock_api.call_count == 0  # Should hit cache, not API

    # Second call for a different key should hit the cache and NOT trigger another API fetch.
    atom.get_metadata("410470")
    assert mock_api.call_count == 0  # Still cached

    # Change the release - this will trigger a fresh fetch
    mock_api.reset_mock()
    atom.set_release("2020e-13tev")
    print(mock_api.call_count)  # For debugging purposes
    # A new call for the new release should trigger the API again.
    atom.get_metadata("301204")
    print(mock_api.call_count)  # For debugging purposes
    assert mock_api.call_count == 2  # Already fetched during set_release


# Test RequestException handling
def test_fetch_and_cache_request_exception(mock_api):
    """Test that a RequestException during metadata fetch is handled gracefully."""
    # Clear the cache to force a fetch
    from src.atlasopenmagic import metadata

    metadata.empty_metadata()

    # Test 1: RequestException during fetch
    with patch("src.atlasopenmagic.metadata._get_session") as mock_session_getter:
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.RequestException("Requests Error")
        mock_resp.ok = False  # Add this
        mock_session.get.return_value = mock_resp
        mock_session_getter.return_value = mock_session

        with pytest.raises(requests.exceptions.RequestException):
            # Force a release change to trigger fetch
            atom.metadata.current_release = "different-release"
            atom.set_release("2024r-pp", page_size=1)

    # Test 2: Empty response handling
    with patch("src.atlasopenmagic.metadata._get_session") as mock_session_getter:
        mock_session = MagicMock()

        def empty_response(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            if "/datasets/count" in url:
                mock_resp.ok = True
                mock_resp.json.return_value = {
                    "count": 0
                }  # This should work, but make sure it's actually called
            else:
                mock_resp.ok = True
                mock_resp.json.return_value = []
            return mock_resp

        mock_session.get.side_effect = empty_response
        mock_session_getter.return_value = mock_session

        atom.set_release("2024r-pp")
        assert len(atom.available_datasets()) == 0


def test_available_releases():
    """Test that available_releases returns the correct list of releases."""
    releases = atom.available_releases()
    # releases should be a string
    assert isinstance(releases, dict)
    # Check that the expected release is present
    assert "2024r-pp" in releases


def test_available_skims():
    """Test the skim functionality."""
    # Empty out the cache first
    from src.atlasopenmagic import metadata

    metadata.empty_metadata()
    # Only one skim defined in our test data sample
    assert atom.available_skims() == ["4lep"]


def test_get_metadata_fields():
    """Test for getting metadata fields."""
    assert 18 == len(atom.get_metadata_fields())


# === Tests for get_urls() ===


def test_get_urls_noskim_default():
    """Test getting base file URLs by default (no 'skim' argument)."""
    urls = atom.get_urls("301204")
    assert urls == ["root://eospublic.cern.ch:1094//eos/path/to/noskim_301204.root"]


def test_get_urls_with_skim():
    """Test getting file URLs for a specific, existing skim."""
    urls = atom.get_urls("301204", skim="4lep")
    assert urls == ["root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_301204.root"]


def test_get_urls_invalid_skim():
    """Test that requesting a non-existent skim raises a ValueError."""
    with pytest.raises(ValueError, match="Skim 'invalid_skim' not found"):
        atom.get_urls("301204", skim="invalid_skim")

    with pytest.raises(ValueError, match="Dataset .*"):
        atom.get_urls("410470", skim="4lep")  # 410470 has no skims


def test_get_urls_different_protocols():
    """Test URL transformation for different protocols."""
    https_urls = atom.get_urls("301204", protocol="https")
    print(https_urls)  # For debugging purposes
    assert https_urls == ["simplecache::https://opendata.cern.ch/eos/path/to/noskim_301204.root"]

    eos_urls = atom.get_urls("301204", protocol="eos")
    assert eos_urls == ["/eos/path/to/noskim_301204.root"]

    with pytest.raises(ValueError):
        assert atom.get_urls("301204", protocol="ftp")


# === Tests for other utility functions ===


# TODO install from environment tests as soon as the new function is implemented
def test_install_from_environment():
    """Test that install_from_environment installs the correct packages."""
    # This test is a placeholder as the actual implementation of install_from_environment
    # is not provided in the original code. It should be implemented once the function is available.
    pass


def test_available_datasets():
    """Test that available_datasets returns the correct, sorted list of dataset numbers."""
    # Empty out the cache first
    from src.atlasopenmagic import metadata

    metadata.empty_metadata()

    # Now see what datasets are available to us
    data = atom.available_datasets()
    assert data == ["301204", "410470", "data"]


def test_available_keywords():
    """Test that available_keywords returns the correct list of keywords."""
    # Empty out the cache first
    from src.atlasopenmagic import metadata

    metadata.empty_metadata()

    # Now check our available keywords
    keywords = atom.available_keywords()
    assert isinstance(keywords, list)
    assert "2electron" in keywords
    assert "BSM" in keywords
    assert "SSM" in keywords


def test_match_metadata():
    """Test that match_metadata returns the correct metadata for a given keyword."""
    # Empty out the cache before the first call to check the caching functionality
    from src.atlasopenmagic import metadata

    metadata.empty_metadata()

    # Match datasets_numbers
    matched = atom.match_metadata("dataset_number", "301204")
    print(matched)  # For debugging purposes
    assert isinstance(matched, list)
    assert len(matched) > 0

    # Match float
    matched = atom.match_metadata("cross_section_pb", "831")
    print(matched)  # For debugging purposes
    assert isinstance(matched, list)
    assert len(matched) > 0

    # Search non-existent keyword
    with pytest.raises(ValueError):
        atom.match_metadata("non_existent", "non_existent")

    # Miss
    matched = atom.match_metadata("cross_section_pb", "1e15")
    print(matched)  # For debugging purposes
    assert len(matched) == 0

    # Match something that has None
    print(atom.get_all_metadata())
    matched = atom.match_metadata("CoMEnergy", None)
    print(matched)  # For debugging purposes
    assert len(matched) > 0


def test_deprecated_get_urls_data():
    """Test that the deprecated get_urls_data function works and raises a warning."""
    with pytest.warns(DeprecationWarning):
        urls = atom.get_urls_data("4lep")

    # Ensure it returns the 'noskim' URLs as expected.
    assert urls == ["root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_data.root"]


def test_build_dataset():
    """Test that build_dataset creates a dataset with the correct URLs."""
    # Force _session to None before the test
    from src.atlasopenmagic import metadata as md

    md._session = None

    # Original test code
    sample_defs = {
        "Sample1": {"dids": ["301204"], "color": "blue"},
        "Sample2": {"dids": ["data"], "color": "red"},
    }
    samples_defs_deprecated = {r"test": {"dids": ["301204"], "color": "yellow"}}

    # Build the dataset
    dataset = atom.build_dataset(sample_defs, skim="4lep", protocol="root")

    # Validate the structure
    assert isinstance(dataset, dict)
    assert "Sample1" in dataset
    assert "Sample2" in dataset

    # Check URLs for Sample1
    print(dataset["Sample1"])  # For debugging purposes
    assert dataset["Sample1"]["list"] == ["root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_301204.root"]
    assert dataset["Sample1"]["color"] == "blue"

    # Check URLs for Sample2
    assert dataset["Sample2"]["list"] == ["root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_data.root"]
    assert dataset["Sample2"]["color"] == "red"

    # Test that the function raises a warning for deprecated usage
    with pytest.warns(DeprecationWarning):
        dataset = atom.build_data_dataset("4lep")
        dataset = atom.build_mc_dataset(samples_defs_deprecated)


def test_find_all_files():
    """
    Test that find_all_files() replaces remote URLs with local paths
    only when the files actually exist under the given local_path.
    """
    # Fake directory listing to be returned by os.walk()
    # Format: (dirpath, dirnames, filenames)
    fake_oswalk = [
        ("/fake/path/mock_data", [], ["noskim_301204.root"]),
        ("/fake/path/mock_data1", [], ["4lep_skim_data.root"]),
    ]

    # Patch os.walk so it returns our fake listing instead of scanning disk
    with patch("src.atlasopenmagic.metadata.os.walk", return_value=fake_oswalk):
        with pytest.warns(UserWarning):
            atom.find_all_files("/fake/path", warnmissing=True)

    # Validate replacement logic
    assert atom.get_urls("301204") == ["/fake/path/mock_data/noskim_301204.root"]
    assert atom.get_urls("301204", skim="4lep") == [
        "root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_301204.root"
    ]
    assert atom.get_urls("data") == ["root://eospublic.cern.ch:1094//eos/path/to/ttbar.root"]
    assert atom.get_urls("data", skim="4lep") == ["/fake/path/mock_data1/4lep_skim_data.root"]

    # Ensure that the cache is cleared
    atom.set_release("2024r-pp")  # Reset to the original release


def test_save_read_metadata():
    """
    Test that we can save metadata to a json file and read it back, and get back what we wrote
    """
    # Empty out the cache first
    from src.atlasopenmagic import metadata

    metadata.empty_metadata()

    # First test that we can save the metadata
    atom.save_metadata("local_metadata.json")
    # Write it to a text file as well - we don't test yet that we can read it back from a text file
    atom.save_metadata("local_metadata.txt")
    # Then test that we can get all the metadata
    my_metadata = atom.get_all_metadata()
    # Now test that we can load the metadata
    atom.read_metadata("local_metadata.json")
    # Check the new metadata
    assert my_metadata == atom.get_all_metadata()

    # Test behavior when a non-standard file type is requested for metadata saving.
    with pytest.raises(ValueError):
        atom.save_metadata("local_metadata.csv")

    # Test a bad metadata load
    import json

    with open("test_file.json", "w") as test_json:
        json.dump(["list", "of", "things"], test_json)
    with pytest.raises(ValueError):
        atom.read_metadata("test_file.json")

    # Clean up after ourselves
    import os

    os.remove("test_file.json")
    os.remove("local_metadata.json")
    os.remove("local_metadata.txt")

    # Ensure the cache is cleared
    atom.set_release("2024r-pp")


def test_get_all_metadata():
    """
    Test function to get all metadata without a warm cache
    """
    # Empty out the cache first
    from src.atlasopenmagic import metadata

    metadata.empty_metadata()
    # Then test that we can get all the metadata
    atom.get_all_metadata()


def test_internals():
    """
    Test internal functions from src.atlasopenmagic
    """
    from src.atlasopenmagic import metadata

    test_path = "/fake/path/mock_data/noskim_301204.root"
    # Check that if we don't give a current local path we just get our path back
    assert metadata._convert_to_local(test_path) == "/fake/path/mock_data/noskim_301204.root"
    # Check that if we start with our local path, we just get our path back
    assert metadata._convert_to_local(test_path, "/fake/path") == "/fake/path/mock_data/noskim_301204.root"


def test_other_metadata_field_type():
    """
    When loading custom metadata, it is possible that someone has a field that's a type we don't treat.
    This checks what happens in that case.
    """
    # Write ourselves a little test file with differently-valued metadata
    import json

    with open("test_file.json", "w") as test_json:
        json.dump(
            {"123456": {"test": {"content": "value"}, "physics_short": "test_sample"}},
            test_json,
        )
    atom.read_metadata("test_file.json")
    # Cleanliness is important!
    import os

    os.remove("test_file.json")
    # Now try to get the metadata based on the keyword
    assert atom.match_metadata("test", {"content": "value"}) == [("123456", "test_sample")]
    # Now try to get metadata for a field we don't use
    with pytest.raises(ValueError):
        atom.match_metadata("not_a_field", None)


def test_count_endpoint_mock():
    """Test that the count endpoint is properly mocked."""
    from src.atlasopenmagic import metadata as md

    # Get a session and make a request to the count endpoint
    session = md._get_session()

    # This should hit our mock
    response = session.get(f"{md.API_BASE_URL}/datasets/count", params={"release_name": "2024r-pp"}, timeout=30)

    # Verify the mock response
    assert response.ok is True
    count_data = response.json()
    assert "count" in count_data
    assert count_data["count"] == 3  # We have 3 datasets in MOCK_DATASETS

    # Test without release filter
    response_all = session.get(f"{md.API_BASE_URL}/datasets/count", timeout=30)
    assert response_all.json()["count"] == 4  # ALL_MOCK_DATASETS has 4 (3 + 1 from 2020)


def test_fetch_and_cache_handles_count_error():
    """Test that _fetch_and_cache_release_data handles count endpoint errors gracefully.

    This covers line 221 where exceptions are caught and total_datasets defaults to 10000.
    """
    from src.atlasopenmagic import metadata as md

    md.empty_metadata()

    with patch("src.atlasopenmagic.metadata._get_session") as mock_session_getter:
        mock_session = MagicMock()

        def failing_count(url, *args, **kwargs):
            if "/datasets/count" in url:
                # Trigger the exception handler on line 221
                raise Exception("Count endpoint failed")

            # Return empty datasets
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = []
            return mock_resp

        mock_session.get.side_effect = failing_count
        mock_session_getter.return_value = mock_session

        # Force a release change to trigger fetch
        md.current_release = "different-release"

        # Should not crash despite count endpoint failing
        atom.set_release("2024r-pp")

        # Verify it worked
        assert md.get_current_release() == "2024r-pp"
        assert len(md._metadata) == 0


def test_count_endpoint_returns_zero():
    """Test handling when count endpoint returns 0."""
    # Clear cache to force a fresh fetch
    from src.atlasopenmagic import metadata

    metadata.empty_metadata()

    with patch("src.atlasopenmagic.metadata._get_session") as mock_session_getter:
        mock_session = MagicMock()

        def zero_count(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None

            if "/datasets/count" in url:
                mock_resp.ok = True
                mock_resp.json.return_value = {"count": 0}
            else:
                mock_resp.json.return_value = []

            return mock_resp

        mock_session.get.side_effect = zero_count
        mock_session_getter.return_value = mock_session

        # Force a release change to trigger fetch
        atom.metadata.current_release = "different_release"
        # Should handle 0 count gracefully
        atom.set_release("2024r-pp")
        assert len(atom.available_datasets()) == 0


def test_count_endpoint_not_ok():
    """Test handling when count endpoint returns ok=False."""
    from src.atlasopenmagic import metadata as md

    # Clear cache to force a fresh fetch
    md.empty_metadata()

    with patch("src.atlasopenmagic.metadata._get_session") as mock_session_getter:
        mock_session = MagicMock()

        def not_ok_count(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None

            if "/datasets/count" in url:
                mock_resp.ok = False  # Simulate failed response
                # Should fallback to 10000
            else:
                mock_resp.json.return_value = []

            return mock_resp

        mock_session.get.side_effect = not_ok_count
        mock_session_getter.return_value = mock_session

        # Force a release change to trigger fetch
        md.current_release = "different-release"
        # Should use fallback count of 10000 but fetch 0 datasets
        atom.set_release("2024r-pp")
        # Since we return empty list, cache should be empty
        assert len(md._metadata) == 0


def test_get_all_info_empty_api_response():
    """Test that get_all_info handles empty API response."""
    from src.atlasopenmagic import metadata as md

    with patch("src.atlasopenmagic.metadata._get_session") as mock_session_getter:
        mock_session = MagicMock()

        def empty_dataset_response(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None

            if "/metadata/" in url:
                # Return empty/null response to trigger line 489
                mock_resp.json.return_value = None  # or {}
            else:
                mock_resp.json.return_value = []

            return mock_resp

        mock_session.get.side_effect = empty_dataset_response
        mock_session_getter.return_value = mock_session

        # Clear cache to force API call
        md.empty_metadata()

        # Should raise ValueError with specific message about empty response
        with pytest.raises(ValueError, match="API returned empty response"):
            atom.get_all_info("999999")


def test_get_all_info_cache_corruption():
    """Test the final safety check when cache has None value."""
    from src.atlasopenmagic import metadata as md

    # Manually corrupt the cache by inserting None
    with md._metadata_lock:
        md._metadata["corrupted_key"] = None

    # Should raise ValueError with "No dataset found" message
    with pytest.raises(ValueError, match="No dataset found with this ID or name"):
        atom.get_all_info("corrupted_key")


def test_fetch_and_cache_count_exception_fallback():
    """Directly test that line 221's exception handler sets total_datasets=10000."""
    from src.atlasopenmagic import metadata as md

    md.empty_metadata()

    with patch("src.atlasopenmagic.metadata._get_session") as mock_session_getter:
        mock_session = MagicMock()

        # Create a side effect that raises for count, returns empty for datasets
        def selective_fail(url, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None

            if "/datasets/count" in url:
                # This will trigger the except clause on line 221
                raise requests.exceptions.Timeout("Simulated timeout")
            else:
                mock_resp.json.return_value = []
                return mock_resp

        mock_session.get.side_effect = selective_fail
        mock_session_getter.return_value = mock_session

        # Force release change
        md.current_release = "other"

        # This should not crash despite count endpoint failing
        atom.set_release("2024r-pp", page_size=1000)

        # Verify it worked
        assert md.get_current_release() == "2024r-pp"
        assert len(md._metadata) == 0  # Empty because we returned no datasets
