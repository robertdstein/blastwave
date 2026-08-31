"""
Tests for the Observation model
"""

# pylint: disable=missing-function-docstring,duplicate-code

import unittest

import numpy as np
import pyarrow as pa

from blastwave.models import Observation


def make_observation(**overrides) -> Observation:
    defaults = dict(  # pylint: disable=use-dict-literal
        jd=2460123.5,
        magpsf=19.5,
        sigmapsf=0.05,
        diffmaglim=20.5,
        ra=150.0,
        dec=20.0,
        snr=8.0,
        band="g",
        survey="ZTF",
        det_type="alert",
        isdiffpos=True,
    )
    defaults.update(overrides)
    return Observation(**defaults)  # type: ignore[arg-type]


class TestObservationComputedFields(unittest.TestCase):
    """
    Tests for Observation computed fields
    """

    def test_mjd(self):
        obs = make_observation(jd=2460123.5)
        self.assertAlmostEqual(obs.mjd, 2460123.5 - 2400000.5)

    def test_estdiffmaglim(self):
        obs = make_observation(magpsf=19.5, snr=8.0)
        expected = 19.5 - 2.5 * float(np.log10(5.0 / 8.0))
        self.assertAlmostEqual(obs.estdiffmaglim, expected)

    def test_estdiffmaglim_at_snr_5_equals_magpsf(self):
        obs = make_observation(magpsf=18.0, snr=5.0)
        self.assertAlmostEqual(obs.estdiffmaglim, 18.0)

    def test_ra_dec_may_be_none(self):
        obs = make_observation(ra=None, dec=None)
        self.assertIsNone(obs.ra)
        self.assertIsNone(obs.dec)

    def test_default_det_type(self):
        obs = Observation(
            jd=2460123.5,
            magpsf=19.5,
            sigmapsf=0.05,
            diffmaglim=20.5,
            ra=150.0,
            dec=20.0,
            snr=8.0,
            band="g",
            survey="ZTF",
            isdiffpos=True,
        )
        self.assertEqual(obs.det_type, "alert")


class TestObservationArrowSchema(unittest.TestCase):
    """
    Tests for Observation.get_arrow_schema
    """

    def test_schema_field_names(self):
        schema = Observation.get_arrow_schema()
        names = set(schema.names)
        for field in Observation.model_fields:  # pylint: disable=not-an-iterable
            self.assertIn(field, names)
        # computed fields are excluded by default
        self.assertNotIn("mjd", names)
        self.assertNotIn("estdiffmaglim", names)

    def test_schema_types(self):
        schema = Observation.get_arrow_schema()
        self.assertEqual(schema.field("jd").type, pa.float64())
        self.assertEqual(schema.field("band").type, pa.string())
        self.assertEqual(schema.field("isdiffpos").type, pa.bool_())
        self.assertTrue(schema.field("jd").nullable)


if __name__ == "__main__":
    unittest.main()
