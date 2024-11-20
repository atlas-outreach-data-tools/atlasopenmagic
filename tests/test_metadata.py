import unittest
from unittest.mock import patch
from atlasopenmagic.metadata import get_metadata, _metadata


class TestGetMetadata(unittest.TestCase):
    def setUp(self):
        """
        Set up mock data for tests by directly assigning to _metadata.
        """
        # Clear and populate _metadata with mock data
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

    def test_get_metadata_full(self):
        """
        Test retrieving full metadata for a dataset number.
        """
        metadata = get_metadata("301204")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["dataset_id"], "301204")
        self.assertEqual(metadata["short_name"], "Pythia8EvtGen_A14MSTW2008LO_Zprime_NoInt_ee_SSM3000")
        self.assertEqual(metadata["cross_section"], "0.001762")

    def test_get_metadata_field(self):
        """
        Test retrieving a specific metadata field.
        """
        cross_section = get_metadata("301204", "cross_section")
        self.assertEqual(cross_section, "0.001762")

    def test_get_metadata_invalid_key(self):
        """
        Test retrieving metadata with an invalid key.
        """
        metadata = get_metadata("invalid_key")
        self.assertIsNone(metadata)

    def test_get_metadata_invalid_field(self):
        """
        Test retrieving an invalid metadata field.
        """
        with self.assertRaises(ValueError):
            get_metadata("301204", "invalid_field")


if __name__ == "__main__":
    unittest.main()
