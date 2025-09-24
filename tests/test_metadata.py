from unittest.mock import MagicMock, patch

import pytest
import requests

import src.atlasopenmagic as atom

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


@pytest.fixture(autouse=True)
def mock_api():
    """
    Pytest fixture to automatically mock requests.get for pagination-aware behavior.
    It slices MOCK_DATASETS based on 'skip' and 'limit' query parameters.
    """

    def get_side_effect(url, params=None, *args, **kwargs):
        skip = int(params.get("skip", 0)) if params else 0
        limit = int(params.get("limit", len(MOCK_DATASETS))) if params else len(MOCK_DATASETS)
        # Slice the datasets according to pagination parameters
        sliced = MOCK_DATASETS[skip : skip + limit]

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = sliced
        return mock_response

    with patch("src.atlasopenmagic.metadata.requests.get") as mock_get:
        mock_get.side_effect = get_side_effect

        # Reset the release, which triggers fetching paginated and caching
        atom.set_release("2024r-pp")
        yield mock_get


# === Tests for get_metadata() ===


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
    with pytest.raises(ValueError, match="Invalid key: 'invalid_key'"):
        atom.get_metadata("invalid_key")


def test_get_metadata_invalid_field():
    """Test that an invalid field name raises a ValueError."""
    with pytest.raises(ValueError, match="Invalid field name: 'invalid_field'"):
        atom.get_metadata("301204", var="invalid_field")


def test_caching_behavior(mock_api):
    """Test that the API is called only twice (once for getting the data, once for exiting the loop)
    for multiple metadata requests within the same release.
    """
    # First call will trigger the API fetch.
    atom.get_metadata("301204")
    assert mock_api.call_count == 2

    # Second call for a different key should hit the cache and NOT trigger another API fetch.
    atom.get_metadata("410470")
    assert mock_api.call_count == 2  # Unchanged!

    # Change the release.
    atom.set_release("2020e-13tev")

    # A new call for the new release should trigger the API again.
    atom.get_metadata("301204")
    assert mock_api.call_count == 4  # Incremented!


# Test RequestException handling
def test_fetch_and_cache_request_exception(mock_api):
    """Test that a RequestException during metadata fetch is handled gracefully."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.exceptions.RequestException("Requests Error")
    mock_api.side_effect = lambda *args, **kwargs: mock_resp  # Always raise the exception

    with pytest.raises(requests.exceptions.RequestException):
        atom.set_release("2024r-pp")

    # Now test the RuntimeError
    mock_resp.raise_for_status.side_effect = None
    mock_resp.raise_for_status.return_value = None
    mock_api.side_effect = lambda *args, **kwargs: mock_resp  # Always return the empty response
    with pytest.raises(RuntimeError):
        atom.set_release("2024r-pp")

    # Flip back to success for the subsequent DSID fetch
    mock_resp.raise_for_status.side_effect = None
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = MOCK_API_RESPONSE


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
    # Define a sample dataset definition
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
