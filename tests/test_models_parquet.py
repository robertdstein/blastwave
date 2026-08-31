"""
Tests for pydantic_to_arrow_schema
"""

# pylint: disable=missing-function-docstring

import unittest

import pyarrow as pa

from blastwave.models import Observation, pydantic_to_arrow_schema
from blastwave.models.source import Source


class TestPydanticToArrowSchema(unittest.TestCase):
    """
    Tests for pydantic_to_arrow_schema
    """

    def test_basic_type_mapping(self):
        schema = pydantic_to_arrow_schema(Observation)
        self.assertEqual(schema.field("jd").type, pa.float64())
        self.assertEqual(schema.field("magpsf").type, pa.float64())
        self.assertEqual(schema.field("band").type, pa.string())
        self.assertEqual(schema.field("isdiffpos").type, pa.bool_())

    def test_unmapped_type_falls_back_to_string(self):
        # det_type is a Literal[...] annotation, not in PYDANTIC_TO_ARROW
        schema = pydantic_to_arrow_schema(Observation)
        self.assertEqual(schema.field("det_type").type, pa.string())

    def test_optional_fields_unwrap_inner_type(self):
        # Source.offset is `float | None`
        schema = pydantic_to_arrow_schema(Source)
        self.assertEqual(schema.field("offset").type, pa.float64())

    def test_excludes_computed_fields_by_default(self):
        schema = pydantic_to_arrow_schema(Source)
        self.assertNotIn("ndethist", schema.names)

    def test_includes_primitive_computed_fields_when_requested(self):
        schema = pydantic_to_arrow_schema(Source, include_computed=True)
        self.assertIn("ndethist", schema.names)
        self.assertEqual(schema.field("ndethist").type, pa.int64())
        self.assertIn("peak_mag", schema.names)
        self.assertEqual(schema.field("peak_mag").type, pa.float64())

    def test_skips_non_primitive_computed_fields(self):
        # `filters` is a computed list[str] field, which has no arrow mapping
        schema = pydantic_to_arrow_schema(Source, include_computed=True)
        self.assertNotIn("filters", schema.names)

    def test_all_fields_nullable(self):
        schema = pydantic_to_arrow_schema(Observation)
        for field in schema:
            self.assertTrue(field.nullable)


if __name__ == "__main__":
    unittest.main()
