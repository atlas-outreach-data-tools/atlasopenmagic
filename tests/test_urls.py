import pytest
from unittest.mock import patch
import atlasopenmagic.metadata as m
from atlasopenmagic.metadata import get_urls, get_urls_data

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

def test_get_urls_root():
    # Default protocol is 'root'
    urls = get_urls(346342)
    assert urls == [
        "root://eospublic.cern.ch//eos/opendata/atlas/rucio/"
        "mc20_13TeV/DAOD_PHYSLITE.37865954._000001.pool.root.1"
    ]

def test_get_urls_https():
    urls = get_urls(346342, protocol="https")
    assert urls == [
        "https://opendata.cern.ch//eos/opendata/atlas/rucio/"
        "mc20_13TeV/DAOD_PHYSLITE.37865954._000001.pool.root.1"
    ]

def test_get_urls_data_invalid_key():
    """Invalid data key should raise ValueError."""
    with pytest.raises(ValueError):
        get_urls_data('THIS_KEY_DOES_NOT_EXIST')

def test_get_urls_data_invalid_protocol():
    """Passing a bad protocol to get_urls_data should raise ValueError."""
    # pick any real key from the current data mapping
    real_key = next(iter(m.url_mapping_data[m.current_release].keys()))
    with pytest.raises(ValueError):
        get_urls_data(real_key, protocol='ftp')

def test_get_urls_data_root():
    # By default (protocol='root'), the first URL should be the EOS root path
    urls = get_urls_data('2015')
    assert urls[0] == (
        "root://eospublic.cern.ch//eos/opendata/atlas/rucio/"
        "data15_13TeV/DAOD_PHYSLITE.37001626._000001.pool.root.1"
    )

def test_get_urls_data_https():
    # When overriding to HTTPS, that same entry should be rewritten
    urls = get_urls_data('2015', protocol="https")
    assert urls[0] == (
        "https://opendata.cern.ch//eos/opendata/atlas/rucio/"
        "data15_13TeV/DAOD_PHYSLITE.37001626._000001.pool.root.1"
    )

# Needs to be last because it changes the release
def get_urls_skim_parameter():
    """
    Verify that get_urls respects the skim argument
    in the 2025e-13tev-beta release.
    """
    # 1) Switch to the beta release
    m.set_release('2025e-13tev-beta')

    # 2) Inject a tiny dummy mapping for our fake dataset code 'XYZ'
    m._url_code_mapping = {
        'XYZ': {
            'noskim': ['root://eospublic.cern.ch/fake/XYZ_noskim.root'],
            'custom': ['root://eospublic.cern.ch/fake/XYZ_custom.root'],
        }
    }
    # 3) Map the user key '123' to our dummy code 'XYZ'
    m.ID_MATCH_LOOKUP['2025e-13tev-beta'] = {'123': 'XYZ'}

    # Default skim should be 'noskim'
    urls = get_urls('123')
    assert urls == ['root://eospublic.cern.ch/fake/XYZ_noskim.root']

    # Override skim explicitly
    urls = get_urls('123', skim='custom')
    assert urls == ['root://eospublic.cern.ch/fake/XYZ_custom.root']

    # Invalid skim name should raise
    with pytest.raises(ValueError):
        get_urls('123', skim='doesNotExist')
