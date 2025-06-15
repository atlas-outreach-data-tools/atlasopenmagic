import pytest
from unittest.mock import patch, Mock
import atlasopenmagic.metadata as m
from atlasopenmagic.metadata import get_urls, get_urls_data

@pytest.fixture
def mock_api_responses():
    """Mock API responses for URL testing."""
    def mock_requests_get(url):
        response = Mock()
        response.raise_for_status = Mock()
        
        if '/700200' in url:
            response.json = Mock(return_value={
                "dataset_number": "700200",
                "physics_short": "Test_Dataset_700200",
                "file_list": [
                    "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000001.pool.root.1",
                    "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000002.pool.root.1",
                    "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000003.pool.root.1",
                ]
            })
        elif '/364710' in url:
            response.json = Mock(return_value={
                "dataset_number": "364710",
                "physics_short": "Test_Dataset_364710",
                "file_list": [
                    "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.38191710._000011.pool.root.1"
                ]
            })
        elif '/346342' in url:
            response.json = Mock(return_value={
                "dataset_number": "346342",
                "physics_short": "Test_Dataset_346342",
                "file_list": [
                    "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37865954._000001.pool.root.1"
                ]
            })
        elif '/data/available' in url:
            response.json = Mock(return_value={
                "available_keys": ["2015", "2016", "2017"]
            })
        elif '/data/2015' in url:
            response.json = Mock(return_value={
                "file_list": [
                    "root://eospublic.cern.ch//eos/opendata/atlas/rucio/data15_13TeV/DAOD_PHYSLITE.37001626._000001.pool.root.1"
                ]
            })
        else:
            # For invalid keys, simulate API error
            response.json = Mock(return_value=None)
            response.raise_for_status = Mock(side_effect=Exception("Not found"))
        
        return response
    
    return mock_requests_get

def test_get_urls_700200(mock_api_responses):
    """
    Test that get_urls for key 700200 returns the expected 3 URLs.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        expected_urls = [
            "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000001.pool.root.1",
            "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000002.pool.root.1",
            "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000003.pool.root.1",
        ]
        urls = get_urls(700200)
        assert len(urls) == 3
        for expected, actual in zip(expected_urls, urls):
            assert expected in actual

def test_get_urls_364710(mock_api_responses):
    """
    Test that get_urls for key 364710 returns the expected single URL.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        expected_url = "DAOD_PHYSLITE.38191710._000011.pool.root.1"
        urls = get_urls(364710)
        assert len(urls) == 1
        assert expected_url in urls[0]

def test_get_urls_with_mock(mock_api_responses):
    """
    Test get_urls using mocked data.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        urls = get_urls(700200)
        assert len(urls) == 3

def test_get_urls_invalid_key(mock_api_responses):
    """
    Test that get_urls with an invalid key raises a ValueError.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        with pytest.raises(ValueError):
            get_urls(999999)

def test_get_urls_empty_key(mock_api_responses):
    """
    Test that get_urls with an empty key raises a ValueError.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        with pytest.raises(ValueError):
            get_urls("")

def test_get_urls_none_key(mock_api_responses):
    """
    Test that get_urls with None as key raises a ValueError.
    """
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        with pytest.raises(ValueError):
            get_urls(None)

def test_get_urls_root(mock_api_responses):
    """Test default protocol is 'root'."""
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        urls = get_urls(346342)
        assert urls == [
            "root://eospublic.cern.ch//eos/opendata/atlas/rucio/"
            "mc20_13TeV/DAOD_PHYSLITE.37865954._000001.pool.root.1"
        ]

def test_get_urls_https(mock_api_responses):
    """Test HTTPS protocol conversion."""
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        urls = get_urls(346342, protocol="https")
        assert urls == [
            "https://opendata.cern.ch//eos/opendata/atlas/rucio/"
            "mc20_13TeV/DAOD_PHYSLITE.37865954._000001.pool.root.1"
        ]

def test_get_urls_data_invalid_key(mock_api_responses):
    """Invalid data key should raise ValueError."""
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        with pytest.raises(ValueError):
            get_urls_data('THIS_KEY_DOES_NOT_EXIST')

def test_get_urls_data_invalid_protocol(mock_api_responses):
    """Passing a bad protocol to get_urls_data should raise ValueError."""
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        with pytest.raises(ValueError):
            get_urls_data('2015', protocol='ftp')

def test_get_urls_data_root(mock_api_responses):
    """Test get_urls_data with root protocol."""
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        urls = get_urls_data('2015')
        assert urls[0] == (
            "root://eospublic.cern.ch//eos/opendata/atlas/rucio/"
            "data15_13TeV/DAOD_PHYSLITE.37001626._000001.pool.root.1"
        )

def test_get_urls_data_https(mock_api_responses):
    """Test get_urls_data with HTTPS protocol."""
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_api_responses):
        urls = get_urls_data('2015', protocol="https")
        assert urls[0] == (
            "https://opendata.cern.ch//eos/opendata/atlas/rucio/"
            "data15_13TeV/DAOD_PHYSLITE.37001626._000001.pool.root.1"
        )

def test_get_urls_skim_parameter():
    """
    Test skim parameter handling in releases that support skims.
    """
    def mock_skim_response(url):
        response = Mock()
        response.raise_for_status = Mock()
        
        if '/123' in url:
            response.json = Mock(return_value={
                "dataset_number": "123",
                "physics_short": "Test_Skim_Dataset",
                "file_list": [
                    "root://eospublic.cern.ch//eos/opendata/atlas/mc/mc_123.test.noskim.root",
                    "root://eospublic.cern.ch//eos/opendata/atlas/mc/mc_123.test.custom.root",
                ]
            })
        return response
    
    with patch('atlasopenmagic.metadata.requests.get', side_effect=mock_skim_response):
        # Switch to a release that supports skims
        m.set_release('2025e-13tev-beta')
        
        # Test default skim
        urls = get_urls('123')
        assert len(urls) >= 1
        
        # Test specific skim
        urls_noskim = get_urls('123', skim='noskim')
        assert len(urls_noskim) == 1
        assert 'noskim' in urls_noskim[0]
        
        # Test invalid skim
        with pytest.raises(ValueError):
            get_urls('123', skim='doesNotExist')
