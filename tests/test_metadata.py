import pytest, requests
from unittest.mock import patch, MagicMock
import atlasopenmagic as atom


# --- Mock API Response ---
# This is a realistic mock of the JSON response from the `/releases/{release_name}` endpoint,
# which the client script's caching function (`_fetch_and_cache_release_data`) calls.
# We are using your provided dataset object as the primary entry in the `datasets` list.
MOCK_API_RESPONSE = {
    "name": "2024r-pp",
    "datasets": [
        # This is the dataset object you provided.
        {
            'dataset_number': '301204',
            'physics_short': 'Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000',
            'e_tag': 'e3723',
            'cross_section_pb': 0.001762,
            'genFiltEff': 1.0,
            'kFactor': 1.0,
            'nEvents': 20000,
            'sumOfWeights': 20000.0,
            'sumOfWeightsSquared': 20000.0,
            'process': 'pp>Zprime>ee',
            'generator': 'Pythia8(v8.186)+EvtGen(v1.2.0)',
            'keywords': ['2electron', 'BSM', 'SSM'],
            'file_list': [
                'root://eospublic.cern.ch:1094//eos/path/to/noskim_301204.root'
            ],
            'description': "Pythia 8 Zprime decaying to two electrons'",
            'job_path': 'https://gitlab.cern.ch/path/to/job/options',
            'release': {'name': '2024r-pp'},
            'skims': [
                {
                    'id': 1,
                    'skim_type': '4lep',
                    'file_list': ['root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_301204.root'],
                    'description': 'Exactly 4 leptons',
                    'dataset_number': '301204',
                    'release_name': '2024r-pp'
                }
            ]
        },
        # Adding a second dataset to make tests for `available_datasets` more robust.
        {
            "dataset_number": "410470",
            "physics_short": "ttbar_lep",
            "cross_section_pb": 831.76,
            "file_list": ["root://eospublic.cern.ch:1094//eos/path/to/ttbar.root"],
            "skims": [],
            "release": {"name": "2024r-pp"}
        },
        {
            "dataset_number": "data",
            "physics_short": "data",
            "cross_section_pb": 831.76,
            "file_list": ["root://eospublic.cern.ch:1094//eos/path/to/ttbar.root"],
            "skims": [
                {
                    "id": 1,
                    "skim_type": "4lep",
                    "file_list": ["root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_data.root"],
                    "description": "Exactly 4 leptons",
                    "dataset_number": "data",
                    "release_name": "2024r-pp"
                }
            ],
            "release": {"name": "2024r-pp"}
        }
    ]
}

@pytest.fixture(autouse=True)
def mock_api():
    """
    Pytest fixture to automatically mock the requests.get call for all tests.
    It also resets the release and clears the cache before each test to ensure isolation.
    """
    with patch("atlasopenmagic.metadata.requests.get") as mock_get:
        mock_response = MagicMock()
        # Default: success behavior
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = MOCK_API_RESPONSE

        mock_get.return_value = mock_response

        # Reset the release (which clears the cache) before each test run.
        atom.set_release("2024r-pp")
        yield mock_get


# === Tests for get_metadata() ===


def test_set_local_release():
    """Test setting a local release and ensuring it clears the cache."""
    with pytest.warns(UserWarning):
        atom.set_release('2024r-pp', 'tests/mock_data')

    assert atom.get_current_release() == '2024r-pp'
    assert atom.get_urls("301204") == ["tests/mock_data/noskim_301204.root"]

    # Now test the 'eos' option
    atom.set_release('2024r-pp', 'eos')
    assert atom.get_urls("301204") == ["/eos/path/to/noskim_301204.root"]

    # Ensure the cache is cleared
    atom.set_release('2024r-pp')  # Reset to the original release


def test_set_wrong_release():
    """Test setting a release that does not exist."""
    with pytest.raises(ValueError):
        atom.set_release('non_existent_release')


def test_get_metadata_no_cache(mock_api):
    """Test retrieving metadata without using cache."""
    # Force only the next HTTP call (direct, no-cache metadata fetch) to fail
    mock_resp = mock_api.return_value
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("Client Error")

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        atom.get_metadata("Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000", cache=False)

    assert "Could not retrieve dataset" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, requests.exceptions.HTTPError)

    # Flip back to success for the subsequent DSID fetch
    mock_resp.raise_for_status.side_effect = None
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = MOCK_API_RESPONSE

    metadata = atom.get_metadata("301204", cache=False)
    assert metadata is not None
    assert metadata["datasets"][0]["dataset_number"] == "301204"



def test_get_metadata_full():
    """Test retrieving the full metadata dictionary for a dataset by its number."""
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
    """Test that the API is called only once for multiple metadata requests within the same release."""
    # First call will trigger the API fetch.
    atom.get_metadata("301204")
    assert mock_api.call_count == 1

    # Second call for a different key should hit the cache and NOT trigger another API fetch.
    atom.get_metadata("410470")
    assert mock_api.call_count == 1  # Unchanged!

    # Change the release.
    atom.set_release('2020e-13tev')

    # A new call for the new release should trigger the API again.
    atom.get_metadata("301204")
    assert mock_api.call_count == 2  # Incremented!


# Test RequestException handling
def test_fetch_and_cache_request_exception(mock_api):
    """Test that a RequestException during metadata fetch is handled gracefully."""
    mock_resp = mock_api.return_value
    mock_resp.raise_for_status.side_effect = requests.exceptions.RequestException("Requests Error")

    with pytest.raises(requests.exceptions.RequestException):
        atom.set_release('2024r-pp')
    
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


# === Tests for get_urls() ===


def test_get_urls_noskim_default():
    """Test getting base file URLs by default (no 'skim' argument)."""
    urls = atom.get_urls("301204")
    assert urls == ["root://eospublic.cern.ch:1094//eos/path/to/noskim_301204.root"]


def test_get_urls_with_skim():
    """Test getting file URLs for a specific, existing skim."""
    urls = atom.get_urls("301204", skim='4lep')
    assert urls == ["root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_301204.root"]


def test_get_urls_invalid_skim():
    """Test that requesting a non-existent skim raises a ValueError."""
    with pytest.raises(ValueError, match="Skim 'invalid_skim' not found"):
        atom.get_urls("301204", skim='invalid_skim')

    with pytest.raises(ValueError, match="Dataset .*"):
        atom.get_urls("410470", skim='4lep')  # 410470 has no skims


def test_get_urls_different_protocols():
    """Test URL transformation for different protocols."""
    https_urls = atom.get_urls("301204", protocol='https')
    print(https_urls)  # For debugging purposes
    assert https_urls == ["https://opendata.cern.ch/eos/path/to/noskim_301204.root"]

    eos_urls = atom.get_urls("301204", protocol='eos')
    assert eos_urls == ["/eos/path/to/noskim_301204.root"]

    with pytest.raises(ValueError):
        assert atom.get_urls("301204", protocol='ftp')


# === Tests for other utility functions ===

# TODO install from environment tests as soon as the new function is implemented
def test_install_from_environment():
    """Test that install_from_environment installs the correct packages."""
    # This test is a placeholder as the actual implementation of install_from_environment
    # is not provided in the original code. It should be implemented once the function is available.
    pass

def test_available_datasets():
    """Test that available_datasets returns the correct, sorted list of dataset numbers."""
    data = atom.available_datasets()
    assert data == ['301204', '410470', 'data']

def test_available_keywords():
    """Test that available_keywords returns the correct list of keywords."""
    
    keywords = atom.available_keywords()
    assert isinstance(keywords, list)
    assert "2electron" in keywords
    assert "BSM" in keywords
    assert "SSM" in keywords


def test_match_metadata():
    """Test that match_metadata returns the correct metadata for a given keyword."""

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
    matched = atom.match_metadata("non_existent", "non_existent")
    print(matched)  # For debugging purposes
    assert matched == []  # Should return an empty list for non-existent keyword
    

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
        "Sample1": {
            "dids": ["301204"],
            "color": "blue"
        },
        "Sample2": {
            "dids": ["data"],
            "color": "red"
        }
    }
    samples_defs_deprecated = {
        r'test': {'dids': ["301204"], 'color': 'yellow'}
        }

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
    with patch("atlasopenmagic.metadata.os.walk", return_value=fake_oswalk):
        with pytest.warns(UserWarning):
            atom.find_all_files("/fake/path", warnmissing=True)

    # Validate replacement logic
    assert atom.get_urls("301204") == ["/fake/path/mock_data/noskim_301204.root"]
    assert atom.get_urls("301204", skim="4lep") == ["root://eospublic.cern.ch:1094//eos/path/to/4lep_skim_301204.root"]
    assert atom.get_urls("data") == ["root://eospublic.cern.ch:1094//eos/path/to/ttbar.root"]
    assert atom.get_urls("data", skim="4lep") == ["/fake/path/mock_data1/4lep_skim_data.root"]

    # atom.set_release('2025e-13tev-beta')  # Reset to the original release
    atom.set_release('2024r-pp')  # Reset to the original release


def test_save_read_metadata():
    """
    Test that we can save metadata to a json file and read it back, and get back what we wrote
    """
    # First test that we can save the metadata
    atom.save_metadata('local_metadata.json')
    # Write it to a text file as well - we don't test yet that we can read it back from a text file
    atom.save_metadata('local_metadata.txt')
    # Then test that we can get all the metadata
    my_metadata = atom.get_all_metadata()
    # Now test that we can load the metadata
    atom.read_metadata('local_metadata.json')
    # Check the new metadata
    assert my_metadata == atom.get_all_metadata()
