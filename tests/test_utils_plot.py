"""
Tests for lightcurve plotting
"""

# pylint: disable=missing-function-docstring,wrong-import-position

import unittest

import matplotlib
import pandas as pd

matplotlib.use("Agg")

from matplotlib import pyplot as plt

from blastwave.utils.plot import plot_lightcurve


class TestPlotLightcurve(unittest.TestCase):
    """
    Tests for plot_lightcurve
    """

    def test_returns_figure(self):
        df = pd.DataFrame(
            {
                "band": ["g", "r"],
                "mjd": [60100.0, 60101.0],
                "magpsf": [19.0, 18.5],
                "sigmapsf": [0.05, 0.04],
            }
        )
        fig = plot_lightcurve(df)
        self.assertIsInstance(fig, plt.Figure)

    def test_figure_is_closed_after_return(self):
        df = pd.DataFrame(
            {"band": ["g"], "mjd": [60100.0], "magpsf": [19.0], "sigmapsf": [0.05]}
        )
        fig = plot_lightcurve(df)
        self.assertNotIn(fig.number, plt.get_fignums())

    def test_handles_empty_dataframe(self):
        df = pd.DataFrame({"band": [], "mjd": [], "magpsf": [], "sigmapsf": []})
        fig = plot_lightcurve(df)
        self.assertIsInstance(fig, plt.Figure)


if __name__ == "__main__":
    unittest.main()
