"""
Script for plotting
"""

import matplotlib.pyplot as plt

colors = {
    "u": "violet",
    "g": "green",
    "r": "red",
    "i": "orange",
    "z": "brown",
    "y": "black",
}


def plot_lightcurve(photometry_df) -> plt.Figure:
    """
    Plot light curve from photometry data frame

    :param photometry_df: DataFrame with photometry data
    :return: Figure with light curve
    """
    fig = plt.figure()
    for filt, c in colors.items():
        mask = photometry_df["band"] == filt
        plt.errorbar(
            photometry_df[mask]["mjd"],
            photometry_df[mask]["magpsf"],
            yerr=photometry_df[mask]["sigmapsf"],
            marker="o",
            linestyle=" ",
            c=c,
            label=filt,
        )

    plt.legend(ncol=2)
    plt.gca().invert_yaxis()
    plt.xlabel("Time [MJD]")
    plt.ylabel("Mag [AB]")
    return fig
