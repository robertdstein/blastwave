"""
Tests for cache path helpers
"""

# pylint: disable=missing-function-docstring

import unittest
from pathlib import Path
from unittest import mock

from blastwave.utils.cache import (
    get_consolidated_source_path,
    get_crossmatch_dir,
    get_crossmatch_path,
    get_data_dir,
    get_photometry_dir,
    get_photometry_path,
    get_source_dir,
    get_source_path,
)


class TestGetDataDir(unittest.TestCase):
    """
    Tests for get_data_dir
    """

    def test_explicit_arg_wins(self):
        self.assertEqual(get_data_dir("/tmp/explicit"), Path("/tmp/explicit"))

    def test_falls_back_to_env_var(self):
        with mock.patch.dict(
            "os.environ", {"BLASTWAVE_DATA_DIR": "/tmp/from_env"}, clear=False
        ):
            self.assertEqual(get_data_dir(), Path("/tmp/from_env"))

    def test_raises_without_arg_or_env(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                get_data_dir()


class TestPathHelpers(unittest.TestCase):
    """
    Tests for the derived path helper functions
    """

    def setUp(self):
        self.base = "/tmp/blastwave_data"

    def test_crossmatch_dir(self):
        self.assertEqual(
            get_crossmatch_dir(self.base), Path(self.base) / "crossmatches"
        )

    def test_crossmatch_path(self):
        self.assertEqual(
            get_crossmatch_path("ZTF1", self.base),
            Path(self.base) / "crossmatches" / "ZTF1.json",
        )

    def test_source_dir(self):
        self.assertEqual(get_source_dir(self.base), Path(self.base) / "sources")

    def test_source_path(self):
        self.assertEqual(
            get_source_path("ZTF1", self.base),
            Path(self.base) / "sources" / "ZTF1.parquet",
        )

    def test_photometry_dir(self):
        self.assertEqual(get_photometry_dir(self.base), Path(self.base) / "photometry")

    def test_photometry_path(self):
        self.assertEqual(
            get_photometry_path("ZTF1", self.base),
            Path(self.base) / "photometry" / "ZTF1.parquet",
        )

    def test_consolidated_source_path(self):
        self.assertEqual(
            get_consolidated_source_path(self.base),
            Path(self.base) / "consolidated_source.parquet",
        )

    def test_object_id_may_be_int(self):
        self.assertEqual(
            get_source_path(313853517419249797, self.base),
            Path(self.base) / "sources" / "313853517419249797.parquet",
        )


if __name__ == "__main__":
    unittest.main()
