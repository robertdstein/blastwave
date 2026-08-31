"""
Tests for BOOM query pydantic models
"""

# pylint: disable=missing-function-docstring,missing-class-docstring,too-few-public-methods

import unittest

from blastwave.models import BOOMQuery, CatalogQuery, FilterQuery


class TestCatalogQuery(unittest.TestCase):
    """
    Tests for CatalogQuery
    """

    def test_requires_catalog_name(self):
        query = CatalogQuery(catalog_name="ZTF_alerts")
        self.assertEqual(query.catalog_name, "ZTF_alerts")

    def test_from_attributes(self):
        class Fake:
            catalog_name = "LSST_alerts"

        query = CatalogQuery.model_validate(Fake(), from_attributes=True)
        self.assertEqual(query.catalog_name, "LSST_alerts")


class TestFilterQuery(unittest.TestCase):
    """
    Tests for FilterQuery
    """

    def test_filter_defaults_to_none(self):
        query = FilterQuery(catalog_name="ZTF_alerts")
        self.assertIsNone(query.filter)

    def test_filter_can_be_set(self):
        query = FilterQuery(
            catalog_name="ZTF_alerts", filter={"objectId": {"$eq": "ZTF1"}}
        )
        self.assertEqual(query.filter, {"objectId": {"$eq": "ZTF1"}})


class TestBOOMQuery(unittest.TestCase):
    """
    Tests for BOOMQuery
    """

    def test_defaults(self):
        query = BOOMQuery(catalog_name="milliquas_v8")
        self.assertIsNone(query.limit)
        self.assertIsNone(query.max_time_ms)
        self.assertIsNone(query.projection)
        self.assertIsNone(query.skip)
        self.assertIsNone(query.sort)

    def test_model_validate_from_dict(self):
        raw = {
            "catalog_name": "milliquas_v8",
            "filter": {"ra": {"$gt": 0}},
            "limit": 3,
            "projection": {"ra": 1, "dec": 1},
        }
        query = BOOMQuery.model_validate(raw)
        self.assertEqual(query.catalog_name, "milliquas_v8")
        self.assertEqual(query.limit, 3)
        self.assertEqual(query.projection, {"ra": 1, "dec": 1})

    def test_model_dump_exclude_none_drops_unset_fields(self):
        query = BOOMQuery(catalog_name="milliquas_v8", limit=3)
        dumped = query.model_dump(exclude_none=True)
        self.assertEqual(dumped, {"catalog_name": "milliquas_v8", "limit": 3})
        self.assertNotIn("skip", dumped)
        self.assertNotIn("sort", dumped)


if __name__ == "__main__":
    unittest.main()
