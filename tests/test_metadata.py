import pytest
from atlasopenmagic.metadata import get_metadata, _metadata

@pytest.fixture
def mock_metadata():
    """
    Fixture to set up mock data for tests by directly assigning to _metadata.
    """
    global _metadata
    _metadata = {
        "301204": {
            "dataset_number": "301204",
            "physics_short": "Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000",
            "crossSection_pb": "0.001762",
            "genFiltEff": "1.0",
            "kFactor": "1.0",
            "nEvents": "20000",
            "sumOfWeights": "20000.0",
        }
    }

def test_get_metadata_full(mock_metadata):
    """
    Test retrieving full metadata for a dataset number.
    """
    metadata = get_metadata("301204")
    assert metadata is not None
    assert metadata["dataset_id"] == "301204"
    assert metadata["short_name"] == "Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000"
    assert metadata["cross_section"] == "0.001762"

def test_get_metadata_field(mock_metadata):
    """
    Test retrieving a specific metadata field.
    """
    cross_section = get_metadata("301204", "cross_section")
    assert cross_section == "0.001762"

def test_get_metadata_invalid_key(mock_metadata):
    """
    Test retrieving metadata with an invalid key.
    """
    with pytest.raises(ValueError):
        get_metadata("invalid_key")

def test_get_metadata_invalid_field(mock_metadata):
    """
    Test retrieving an invalid metadata field.
    """
    with pytest.raises(ValueError):
        get_metadata("301204", "invalid_field")

def test_get_metadata_no_field(mock_metadata):
    """
    Test retrieving metadata without specifying a field.
    """
    metadata = get_metadata("301204")
    assert metadata is not None
    assert "dataset_id" in metadata
    assert "short_name" in metadata

def test_get_metadata_partial_field(mock_metadata):
    """
    Test retrieving a partial metadata field.
    """
    physics_short = get_metadata("301204", "short_name")
    assert physics_short == "Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000"

def test_get_metadata_case_insensitive(mock_metadata):
    """
    Test retrieving metadata with case insensitive field.
    """
    cross_section = get_metadata("301204", "Cross_Section")
    assert cross_section == "0.001762"
