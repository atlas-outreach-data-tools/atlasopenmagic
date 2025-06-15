import pytest
from unittest.mock import patch, Mock
from atlasopenmagic.metadata import get_metadata

@pytest.fixture
def mock_api_response():
    """
    Fixture to mock API responses for testing.
    """
    def mock_requests_get(url):
        response = Mock()
        response.raise_for_status = Mock()
        
        if '/301204' in url:
            response.json = Mock(return_value={
                "dataset_number": "301204",
                "physics_short": "Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000",
                "crossSection_pb": "0.001762",
                "genFiltEff": "1.0",
                "kFactor": "1.0",
                "nEvents": "20000",
                "sumOfWeights": "20000.0",
                "sumOfWeightsSquared": "20000.0",
                "process": "pp>Zprime>ee",
                "generator": "Pythia8+EvtGen",
                "keywords": "['BSM', 'Zprime']",
                "description": "Pythia 8 Zprime decaying to two electrons",
                "job_path": "https://example.com/job",
                "file_list": [
                    "root://eospublic.cern.ch//eos/opendata/atlas/test1.root",
                    "root://eospublic.cern.ch//eos/opendata/atlas/test2.root"
                ]
            })
        else:
            # For invalid keys, return None to simulate API error
            response.json = Mock(return_value=None)
            response.raise_for_status = Mock(side_effect=Exception("Not found"))
        
        return response
    
    return mock_requests_get

def test_get_metadata_full(mock_api_response):
    """
    Test retrieving full metadata for a dataset number.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_response):
        metadata = get_metadata("301204")
        assert metadata is not None
        assert metadata["dataset_id"] == "301204"
        assert metadata["short_name"] == "Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000"
        assert metadata["cross_section"] == "0.001762"

def test_get_metadata_field(mock_api_response):
    """
    Test retrieving a specific metadata field.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_response):
        cross_section = get_metadata("301204", "cross_section")
        assert cross_section == "0.001762"

def test_get_metadata_invalid_key(mock_api_response):
    """
    Test retrieving metadata with an invalid key.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_response):
        with pytest.raises(ValueError):
            get_metadata("invalid_key")

def test_get_metadata_invalid_field(mock_api_response):
    """
    Test retrieving an invalid metadata field.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_response):
        with pytest.raises(ValueError):
            get_metadata("301204", "invalid_field")

def test_get_metadata_no_field(mock_api_response):
    """
    Test retrieving metadata without specifying a field.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_response):
        metadata = get_metadata("301204")
        assert metadata is not None
        assert "dataset_id" in metadata
        assert "short_name" in metadata

def test_get_metadata_partial_field(mock_api_response):
    """
    Test retrieving a partial metadata field.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_response):
        physics_short = get_metadata("301204", "short_name")
        assert physics_short == "Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000"

def test_get_metadata_case_insensitive(mock_api_response):
    """
    Test retrieving metadata with case insensitive field.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_response):
        cross_section = get_metadata("301204", "Cross_Section")
        assert cross_section == "0.001762"
