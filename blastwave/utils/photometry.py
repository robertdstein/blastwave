"""
Scripts for combining photometry
"""

import numpy as np
import pandas as pd


def deduplicate_ztf_photometry(full_data: dict) -> pd.DataFrame:
    """
    Deduplicate ZTF photometry by removing entries in fp_hists
    that have the same jd as entries in prv_candidates.

    :param full_data: Full ZTF alert data
    :return: Dataframe of deduplicated ZTF photometry
    """
    df = pd.DataFrame(full_data["prv_candidates"])

    fp_df = pd.DataFrame(full_data["fp_hists"])

    if len(fp_df) > 0:
        mask = ~fp_df["jd"].isin(df["jd"])
        if mask.any():
            df = pd.concat([df, fp_df[mask]], ignore_index=True)

    ul_df = pd.DataFrame(full_data["prv_nondetections"])

    if len(ul_df) > 0:
        mask = ~ul_df["jd"].isin(df["jd"])
        if mask.any():
            df = pd.concat([df, ul_df[mask]], ignore_index=True)

    df = df[[x for x in df.columns if x not in ["snr"]]]

    df = (
        df.sort_values(by="jd")
        .reset_index(drop=True)
        .replace({None: np.nan})
        .rename(
            columns={
                "psfFlux": "psf_flux",
                "psfFluxErr": "psf_flux_err",
                "snr_psf": "snr",
            }
        )
    )
    df["isdiffpos"] = df["psf_flux"] > 0.0

    return df


def deduplicate_lsst_photometry(full_data: dict) -> pd.DataFrame:
    """
    Deduplicate LSST photometry by removing entries in fp_hists
    that have the same jd as entries in prv_candidates.

    :param full_data: Full LSST alert data
    :return: Dataframe of deduplicated LSST photometry
    """
    df = pd.DataFrame(full_data["prv_candidates"])

    fp_df = pd.DataFrame(full_data["fp_hists"])
    fp_df.rename(columns={"snr_psf": "snr"}, inplace=True)

    if len(fp_df) > 0:
        mask = ~fp_df["jd"].isin(df["jd"])
        if mask.any():
            df = pd.concat([df, fp_df[mask]], ignore_index=True)

    df = (
        df.sort_values(by="jd")
        .reset_index(drop=True)
        .replace({None: np.nan})
        .rename(
            columns={
                "psfFlux": "psf_flux",
                "psfFluxErr": "psf_flux_err",
            }
        )
    )
    df["isdiffpos"] = df["psf_flux"] > 0.0
    return df
