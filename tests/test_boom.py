"""
Script to test BOOM
"""

import logging
import os
import time
import unittest

from blastwave import BoomClient

logger = logging.getLogger(__name__)

RUN_LIVE_TESTS = os.getenv("BOOM_LIVE_TESTS") == "1"


@unittest.skipUnless(
    RUN_LIVE_TESTS, "Set BOOM_LIVE_TESTS=1 to run tests against the live BOOM API"
)
class TestAPI(unittest.TestCase):
    """
    Class for testing API
    """

    boom = BoomClient()

    def test_ping(self):
        """
        Test ping

        :return: None
        """
        logger.info("Testing the ping")
        assert self.boom.ping(), "Server not reached"
        time.sleep(3)

    def test_catalogs(self):
        """
        Test catalogs

        :return: None
        """
        logger.info("Testing the catalogs")

        cats = self.boom.get_catalogs()
        assert cats, "No catalogs found"

        catalog = "CatWISE2020"
        assert catalog in cats, f"{catalog} not found"

        n_entries = self.boom.get_entry_count(catalog)
        n_expected = 2224655225

        assert (
            n_entries == n_expected
        ), f"{catalog} entries  of {n_entries} did not match {n_expected}"

        ra, dec = 191.6182623, -1.7184336

        res = self.boom.cone_search(
            ra, dec, radius_arcsec=20.0, catalog=catalog, limit=None
        )

        assert len(res) == 2, f"Unexpected matches: {res}"
        assert (
            res[1]["source_name"] == "J124628.83-014305.3"
        ), f"Unexpected matches: {res}"

        time.sleep(3)
