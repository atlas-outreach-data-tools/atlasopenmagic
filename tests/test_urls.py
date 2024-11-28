import unittest
from atlasopenmagic.urls import get_urls
from unittest.mock import patch

class TestGetUrls(unittest.TestCase):
    def test_get_urls_700200(self):
        """
        Test that get_urls for key 700200 returns the expected 3 URLs.
        """
        expected_urls = [
            "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000001.pool.root.1",
            "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000002.pool.root.1",
            "root://eospublic.cern.ch//eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37110878._000003.pool.root.1",
        ]
        urls = get_urls(700200)
        self.assertEqual(len(urls), 3)
        for expected, actual in zip(expected_urls, urls):
            self.assertIn(expected, actual)

    def test_get_urls_364710(self):
        """
        Test that get_urls for key 364710 returns the expected single URL.
        """
        expected_url = "DAOD_PHYSLITE.38191710._000011.pool.root.1"
        urls = get_urls(364710)
        self.assertEqual(len(urls), 1)
        self.assertIn(expected_url, urls[0])
    
    @patch("atlasopenmagic.urls._load_url_code_mapping")
    def test_get_urls_with_mock(self, mock_load):
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
        print(get_urls(105985))
        urls = get_urls(700200)
        self.assertEqual(len(urls), 3)

if __name__ == '__main__':
    unittest.main()
