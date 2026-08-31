"""
Tests for combining cached sources into a single parquet file
"""

# pylint: disable=missing-function-docstring

import tempfile
import unittest
from unittest import mock

import pandas as pd

from blastwave.utils.cache import get_source_dir
from blastwave.utils.combine import combine_sources, load_consolidated_sources


class TestCombineSources(unittest.TestCase):
    """
    Tests for combine_sources / load_consolidated_sources
    """

    def test_combines_per_object_parquet_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = get_source_dir(tmp)
            source_dir.mkdir(parents=True)

            pd.DataFrame([{"objectid": "obj1", "peak_mag": 19.0}]).to_parquet(
                source_dir / "obj1.parquet"
            )
            pd.DataFrame([{"objectid": "obj2", "peak_mag": 18.0}]).to_parquet(
                source_dir / "obj2.parquet"
            )

            combine_sources(tmp)
            df = load_consolidated_sources(tmp)

        self.assertEqual(len(df), 2)
        self.assertEqual(set(df["objectid"]), {"obj1", "obj2"})

    def test_default_data_dir_uses_env_var(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict("os.environ", {"BLASTWAVE_DATA_DIR": tmp}):
                source_dir = get_source_dir()
                source_dir.mkdir(parents=True)
                pd.DataFrame([{"objectid": "obj1", "peak_mag": 19.0}]).to_parquet(
                    source_dir / "obj1.parquet"
                )

                combine_sources()
                df = load_consolidated_sources()

            self.assertEqual(len(df), 1)
            self.assertEqual(df.iloc[0]["objectid"], "obj1")


if __name__ == "__main__":
    unittest.main()
