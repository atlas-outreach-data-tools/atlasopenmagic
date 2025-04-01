import pytest
from unittest.mock import patch
from atlasopenmagic.metadata import get_urls

def test_get_urls_700200():
    """
    Test that get_urls for key 700200 returns the expected 3 URLs.
    """
    expected_urls = [
        "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000001.pool.root.1",
        "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000002.pool.root.1",
        "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000003.pool.root.1",
    ]
    urls = get_urls(700200)
    assert len(urls) == 3
    for expected, actual in zip(expected_urls, urls):
        assert expected in actual

def test_get_urls_364710():
    """
    Test that get_urls for key 364710 returns the expected single URL.
    """
    expected_url = "DAOD_PHYSLITE.38191710._000011.pool.root.1"
    urls = get_urls(364710)
    assert len(urls) == 1
    assert expected_url in urls[0]

@patch("atlasopenmagic.metadata._load_url_code_mapping")
def test_get_urls_with_mock(mock_load):
    """
    Test get_urls using mocked data.
    """
    mock_load.return_value = {
        "700200": [
            "DAOD_PHYSLITE.37110878._000001.pool.root.1",
            "DAOD_PHYSLITE.37110878._000002.pool.root.1",
            "DAOD_PHYSLITE.37110878._000003.pool.root.1",
        ]
    }
    urls = get_urls(700200)
    assert len(urls) == 3

def test_get_urls_invalid_key():
    """
    Test that get_urls with an invalid key raises a ValueError.
    """
    with pytest.raises(ValueError):
        get_urls(999999)

def test_get_urls_empty_key():
    """
    Test that get_urls with an empty key returns an empty list.
    """
    with pytest.raises(ValueError):
        get_urls("")

def test_get_urls_none_key():
    """
    Test that get_urls with None as key returns an empty list.
    """
    with pytest.raises(ValueError):
        get_urls(None)
