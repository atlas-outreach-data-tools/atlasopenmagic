import pytest
from unittest.mock import patch, MagicMock
import atlasopenmagic.metadata as aom

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
                'root://eospublic.cern.ch:1094//path/to/noskim_301204.root'
            ],
            'description': "Pythia 8 Zprime decaying to two electrons'",
            'job_path': 'https://gitlab.cern.ch/path/to/job/options',
            'release': {'name': '2024r-pp'},
            'skims': [
                {
                    'id': 1,
                    'skim_type': '4lep',
                    'file_list': ['root://eospublic.cern.ch:1094//path/to/4lep_skim_301204.root'],
                    'description': 'Exactly 4 leptons',
                    'dataset_number': '301204',
                    'release_name': '2024r-pp'
                }
            ]
        },
        # Adding a second dataset to make tests for `available_data` more robust.
        {
            "dataset_number": "410470",
            "physics_short": "ttbar_lep",
            "cross_section_pb": 831.76,
            "file_list": ["root://eospublic.cern.ch:1094//path/to/ttbar.root"],
            "skims": [],
            "release": {"name": "2024r-pp"}
        }
    ]
}

@pytest.fixture(autouse=True)
def mock_api(monkeypatch):
    """
    Pytest fixture to automatically mock the requests.get call for all tests.
    It also resets the release and clears the cache before each test to ensure isolation.
    """
    with patch('atlasopenmagic.metadata.requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = MOCK_API_RESPONSE
        mock_get.return_value = mock_response

        # Reset the release (which clears the cache) before each test run.
        aom.set_release('2024r-pp')
        yield mock_get

# === Tests for get_metadata() ===

def test_get_metadata_full():
    """Test retrieving the full metadata dictionary for a dataset by its number."""
    metadata = aom.get_metadata("301204")
    assert metadata is not None
    assert metadata["dataset_number"] == "301204"
    assert metadata["physics_short"] == "Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000"
    assert metadata["cross_section_pb"] == 0.001762

def test_get_metadata_by_short_name():
    """Test retrieving metadata using the physics_short name."""
    metadata = aom.get_metadata("Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000")
    assert metadata is not None
    assert metadata["dataset_number"] == "301204"

def test_get_metadata_specific_field():
    """Test retrieving a single, specific metadata field using the new API name."""
    cross_section = aom.get_metadata("301204", var="cross_section_pb")
    assert cross_section == 0.001762

def test_get_metadata_invalid_key():
    """Test that an invalid dataset key raises a ValueError."""
    with pytest.raises(ValueError, match="Invalid key: 'invalid_key'"):
        aom.get_metadata("invalid_key")

def test_get_metadata_invalid_field():
    """Test that an invalid field name raises a ValueError."""
    with pytest.raises(ValueError, match="Invalid field name: 'invalid_field'"):
        aom.get_metadata("301204", var="invalid_field")

def test_caching_behavior(mock_api):
    """Test that the API is called only once for multiple metadata requests within the same release."""
    # First call will trigger the API fetch.
    aom.get_metadata("301204")
    assert mock_api.call_count == 1

    # Second call for a different key should hit the cache and NOT trigger another API fetch.
    aom.get_metadata("410470")
    assert mock_api.call_count == 1  # Unchanged!

    # Change the release.
    aom.set_release('2020e-13tev')

    # A new call for the new release should trigger the API again.
    aom.get_metadata("301204")
    assert mock_api.call_count == 2  # Incremented!

# === Tests for get_urls() ===

def test_get_urls_noskim_default():
    """Test getting base file URLs by default (no 'skim' argument)."""
    urls = aom.get_urls("301204")
    assert urls == ["root://eospublic.cern.ch:1094//path/to/noskim_301204.root"]

def test_get_urls_with_skim():
    """Test getting file URLs for a specific, existing skim."""
    urls = aom.get_urls("301204", skim='4lep')
    assert urls == ["root://eospublic.cern.ch:1094//path/to/4lep_skim_301204.root"]

def test_get_urls_invalid_skim():
    """Test that requesting a non-existent skim raises a ValueError."""
    with pytest.raises(ValueError, match="Skim 'invalid_skim' not found"):
        aom.get_urls("301204", skim='invalid_skim')

def test_get_urls_different_protocols():
    """Test URL transformation for different protocols."""
    https_urls = aom.get_urls("301204", protocol='https')
    print(https_urls)  # For debugging purposes
    assert https_urls == ["https://opendata.cern.ch/path/to/noskim_301204.root"]

    eos_urls = aom.get_urls("301204", protocol='eos')
    assert eos_urls == ["/path/to/noskim_301204.root"]

# === Tests for other utility functions ===

def test_available_data():
    """Test that available_data returns the correct, sorted list of dataset numbers."""
    data = aom.available_data()
    assert data == ['301204', '410470']

def test_deprecated_get_urls_data():
    """Test that the deprecated get_urls_data function works and raises a warning."""
    with pytest.warns(DeprecationWarning):
        urls = aom.get_urls_data("301204")
    
    # Ensure it returns the 'noskim' URLs as expected.
    assert urls == ["root://eospublic.cern.ch:1094//path/to/noskim_301204.root"]
