"""
Model for a Source
"""

import logging

import pandas as pd
from babamul.models import LsstAlert, ZtfAlert
from matplotlib import pyplot as plt
from pydantic import BaseModel, computed_field

from blastwave.models.observation import Observation
from blastwave.utils import plot_lightcurve

logger = logging.getLogger(__name__)


class Source(BaseModel):
    """
    Model for a Source
    """

    objectid: int | str
    jd: float
    ztfid: str | None
    lsstid: str | None
    ra: float
    dec: float
    offset: float | None
    host_origin: str | None

    photometry: list[Observation]

    @computed_field
    @property
    def ndethist(self) -> int:
        """
        Get number of positive detections

        :return: Number of positive detections
        """
        return len(self.get_detections())

    @computed_field
    @property
    def filters(self) -> list[str]:
        """
        Get list of unique filters in detections

        :return: List of unique filters
        """
        return list(set(self.get_detections()["band"]))

    @computed_field
    @property
    def ndetfilters(self) -> int:
        """
        Get number of unique filters in detections

        :return: Number of unique filters
        """
        return len(self.filters)

    @computed_field
    @property
    def jdstarthist(self) -> float:
        """
        Get JD of first positive detection

        :return: JD of first positive detection
        """
        return self.get_detections()["jd"].min()

    @computed_field
    @property
    def jdendhist(self) -> float:
        """
        Get JD of last positive detection

        :return: JD of last positive detection
        """
        return self.get_detections()["jd"].max()

    @computed_field
    @property
    def age(self) -> float:
        """
        Get age of source in days (time between first and last positive detection)

        :return: Age of source in days
        """
        return self.jdendhist - self.jdstarthist

    def get_photometry(self) -> pd.DataFrame:
        """
        Get photometry as DataFrame

        :return: DataFrame of photometry
        """
        return pd.DataFrame([x.model_dump() for x in self.photometry])

    def get_detections(self, min_snr: float = 3.0) -> pd.DataFrame:
        """
        Get positive detections from photometry

        :param min_snr: Minimum SNR of positive detections
        :return: DataFrame of positive detections
        """
        df = self.get_photometry()
        positive_det_mask = (
            df["isdiffpos"].astype(bool)
            & (pd.notnull(df["magpsf"]))
            & (df["snr"] > min_snr)
        )
        return df[positive_det_mask].reset_index(drop=True)

    # @classmethod
    # def from_lsst(cls, lsst_id: int | str) -> "Source":
    #     """
    #     Create Source object from raw LSST alert
    #
    #     :param lsst_id: LSST object ID
    #     :return: Source object
    #     """
    #
    #     alert = get_object(
    #         "LSST",
    #         object_id=str(lsst_id),
    #     )
    #
    #     photometry = [x.model_dump() for x in alert.get_photometry()]
    #
    #     lsst_df = pd.DataFrame(photometry)
    #     lsst_df["survey"] = "lsst"
    #
    #     extra_df = get_extra_df(alert)
    #
    #     photometry = convert_photometry(lsst_df, extra_df)
    #
    #     return cls(
    #         objectid=alert.objectId,
    #         lsstid=alert.objectId,
    #         ztfid=(
    #             alert.survey_matches.ztf.objectId
    #             if alert.survey_matches.ztf is not None
    #             else None
    #         ),
    #         photometry=photometry,
    #         **alert.candidate.model_dump(),
    #     )

    @classmethod
    def from_lsst(cls, full_data: dict, photometry_df: pd.DataFrame) -> "Source":
        """
        Create Source object from raw ZTF alert

        :param full_data: Full alert data
        :param photometry_df: Photometry data
        :return: Source object
        """

        alert = LsstAlert(**full_data)

        try:
            ztf_id = full_data["aliases"]["LSST"][0]
        except (IndexError, KeyError):
            ztf_id = None

        photometry = [
            Observation(**row) for row in photometry_df.to_dict(orient="records")
        ]

        # Add in something
        offset = None
        offset_origin = None

        return cls(
            objectid=alert.objectId,
            lsstid=alert.objectId,
            ztfid=ztf_id,
            photometry=photometry,
            offset=offset,
            host_origin=offset_origin,
            **alert.candidate.model_dump(),
        )

    @classmethod
    def from_ztf(cls, full_data: dict, photometry_df: pd.DataFrame) -> "Source":
        """
        Create Source object from raw ZTF alert

        :param full_data: Full alert data
        :param photometry_df: Photometry data
        :return: Source object
        """
        alert = ZtfAlert(**full_data)

        try:
            lsst_id = full_data["aliases"]["LSST"][0]
        except (IndexError, KeyError):
            lsst_id = None

        photometry = [
            Observation(**row) for row in photometry_df.to_dict(orient="records")
        ]

        return cls(
            objectid=alert.objectId,
            lsstid=lsst_id,
            ztfid=alert.objectId,
            photometry=photometry,
            offset=alert.candidate.distpsnr1,
            host_origin="PS1",
            **alert.candidate.model_dump(),
        )

    def show_lightcurve(self, min_snr: float = 3.0) -> plt.Figure:
        """
        Helper function for plotting lightcurve of source.

        :param min_snr: Minimum SNR of positive detections
        :return: Figure of light curve
        """
        df = self.get_detections(min_snr=min_snr)
        return plot_lightcurve(df)

    # @classmethod
    # def from_alert(cls, raw_alert, category: str) -> "Source":
    #     """
    #     Create Source object from raw alert based on category
    #
    #     :param raw_alert: Raw alert data
    #     :param category: Category of alert ("lsst" or "ztf")
    #     :return: Source object
    #     """
    #     if category == "lsst":
    #         return cls.from_lsst(raw_alert)
    #     elif category == "ztf":
    #         return cls.from_ztf(raw_alert)
    #     else:
    #         err = f"Unrecognised category {category}"
    #         logger.error(err)
    #         raise ValueError(err)

    # def to_archive(self):
    #     """
    #     Dump Source object to dictionary in archive format,
    #     with photometry as list of dictionaries
    #
    #     :return: Dictionary in archive format
    #     """
    #
    #     output_path = babamul_cache_dir / f"{self.objectid}.json"
    #     res = self.model_dump()
    #     with open(output_path, "w") as f:
    #         json.dump(res, f, indent=4)
    #
    # def convert_to_ztfstyle(self) -> dict:
    #     res = self.model_dump()
    #     cand = {key: val for key, val in res.items() if key not in ["photometry"]}
    #     res["candidate"] = cand
    #     res["objectId"] = self.objectid
    #
    #     df = self.get_detections()
    #
    #     df["fid"] = df["band"].map(FID_MAPPING).astype("Int8")
    #     df["filter"] = df["band"]
    #
    #     match = df.iloc[-1]
    #
    #     res["candidate"].update(match.to_dict())
    #     res["prv_candidates"] = df[:-1].to_dict(orient="records")
    #
    #     return res
