"""
Tests for the ZTF/LSST projection dictionaries used to trim aux queries
"""

# pylint: disable=missing-function-docstring

import unittest

from blastwave.projections import lsst_aux_projection, ztf_aux_projection
from blastwave.projections.ztf import ztf_alert_projection


class TestLsstAuxProjection(unittest.TestCase):
    """
    Tests for lsst_aux_projection
    """

    def test_all_values_are_one(self):
        self.assertTrue(all(v == 1 for v in lsst_aux_projection.values()))

    def test_covers_both_prefixes(self):
        keys = lsst_aux_projection.keys()
        self.assertTrue(any(k.startswith("prv_candidates.") for k in keys))
        self.assertTrue(any(k.startswith("fp_hists.") for k in keys))

    def test_includes_aliases(self):
        self.assertEqual(lsst_aux_projection["aliases"], 1)

    def test_includes_expected_field(self):
        self.assertIn("prv_candidates.reliability", lsst_aux_projection)
        self.assertIn("fp_hists.reliability", lsst_aux_projection)


class TestZtfAuxProjection(unittest.TestCase):
    """
    Tests for ztf_aux_projection
    """

    def test_all_values_are_one(self):
        self.assertTrue(all(v == 1 for v in ztf_aux_projection.values()))

    def test_covers_all_prefixes(self):
        keys = ztf_aux_projection.keys()
        for prefix in ["prv_candidates.", "fp_hists.", "prv_nondetections."]:
            self.assertTrue(any(k.startswith(prefix) for k in keys))

    def test_includes_aliases_and_crossmatches(self):
        self.assertEqual(ztf_aux_projection["aliases"], 1)
        self.assertEqual(ztf_aux_projection["cross_matches"], 1)


class TestZtfAlertProjection(unittest.TestCase):
    """
    Tests for ztf_alert_projection
    """

    def test_has_expected_candidate_fields(self):
        self.assertEqual(ztf_alert_projection["objectId"], 1)
        self.assertEqual(ztf_alert_projection["candidate.jd"], 1)
        self.assertEqual(ztf_alert_projection["candidate.ra"], 1)
        self.assertEqual(ztf_alert_projection["candidate.dec"], 1)


if __name__ == "__main__":
    unittest.main()
