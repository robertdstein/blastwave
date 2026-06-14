"""
Model for a Source
"""

import json
import logging
from pathlib import Path

import pandas as pd
from babamul.models import LsstAlert
from matplotlib import pyplot as plt
from pydantic import BaseModel, computed_field

from blastwave.models.observation import Observation
from blastwave.utils import (
    get_crossmatch_path,
    get_photometry_path,
    get_source_path,
    plot_lightcurve,
)

logger = logging.getLogger(__name__)


class Source(BaseModel):
    """
    Model for a Source
    """

    objectid: int | str
    jd: float
    ztfid: str | None = None
    lsstid: str | None = None
    tns_name: str | None = None
    ra: float
    dec: float
    offset: float | None
    host_origin: str | None
    redshift: float | None = None
    redshift_error: float | None = None
    redshift_origin: str | None = None
    photometry: list[Observation]
    crossmatches: dict[str, list[dict]] | None = None

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
        return float(self.get_detections()["jd"].min())

    @computed_field
    @property
    def jdendhist(self) -> float:
        """
        Get JD of last positive detection

        :return: JD of last positive detection
        """
        return float(self.get_detections()["jd"].max())

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
            & ~(df["magpsf"] > (df["diffmaglim"] + 1.0))
        )
        return df[positive_det_mask].reset_index(drop=True)

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
        redshift = None
        redshift_error = None
        redshift_origin = None

        crossmatches = full_data["cross_matches"]
        for key in ["NED", "LSPSC", "PS1_DR1"]:
            if key in crossmatches:
                if len(crossmatches[key]) > 0:
                    match = crossmatches[key][0]
                    offset = match["distance_arcsec"]
                    offset_origin = key
                    if "z" in match:
                        redshift = match["z"]
                        redshift_error = match["z_unc"]
                        redshift_origin = f"{key}_{match["z_tech"]}"
                    break

        return cls(
            objectid=alert.objectId,
            lsstid=alert.objectId,
            ztfid=ztf_id,
            photometry=photometry,
            offset=offset,
            host_origin=offset_origin,
            crossmatches=crossmatches,
            redshift=redshift,
            redshift_error=redshift_error,
            redshift_origin=redshift_origin,
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
        object_id = full_data["objectId"]

        try:
            lsst_id = full_data["aliases"]["LSST"][0]
        except (IndexError, KeyError):
            lsst_id = None

        photometry = [
            Observation(**row) for row in photometry_df.to_dict(orient="records")
        ]

        return cls(
            objectid=object_id,
            lsstid=lsst_id,
            ztfid=object_id,
            photometry=photometry,
            offset=full_data["candidate"]["distpsnr1"],
            host_origin="PS1",
            ra=full_data["candidate"]["ra"],
            dec=full_data["candidate"]["dec"],
            jd=full_data["candidate"]["jd"],
            crossmatches=full_data["cross_matches"],
        )

    def show_lightcurve(self, min_snr: float = 3.0) -> plt.Figure:
        """
        Helper function for plotting lightcurve of source.

        :param min_snr: Minimum SNR of positive detections
        :return: Figure of light curve
        """
        df = self.get_detections(min_snr=min_snr)
        return plot_lightcurve(df)

    def get_trimmed_photometry(self, min_snr: float = 3.0) -> list[Observation]:
        """
        Trim photometry from source

        :param min_snr: Minimum SNR of positive detections
        :return: list of trimmed Observations
        """
        photometry_df = self.get_detections(min_snr=min_snr)
        return [Observation(**row) for row in photometry_df.to_dict(orient="records")]

    def to_json(self, trim_photometry: bool = True) -> str:
        """
        Convert to JSON

        :return: JSON representation of Source
        """
        data = self.model_dump(
            mode="json", exclude_defaults=True, exclude_computed_fields=True
        )
        df = (
            self.get_detections(min_snr=3.0)
            if trim_photometry
            else self.get_photometry()
        )
        df = df[list(Observation.model_fields.keys())]
        data["photometry"] = df.to_dict(orient="list")
        return json.dumps(data)

    @classmethod
    def from_json(cls, data: str) -> "Source":
        """
        Create Source object from JSON

        :param data: JSON representation of Source
        :return: Source object
        """
        d = json.loads(data)
        photometry_df = pd.DataFrame(d.pop("photometry"))
        photometry = [
            Observation(**row) for row in photometry_df.to_dict(orient="records")
        ]
        return cls(**d, photometry=photometry)

    def to_parquet(
        self, base_path: Path | str | None = None, trim_photometry: bool = True
    ) -> None:
        """
        Export photometry as parquet file

        :param base_path: Base directory
        :param trim_photometry: Store only positive detections
        :return: None
        """
        source_path = get_source_path(self.objectid, base_path)
        crossmatch_path = get_crossmatch_path(self.objectid, base_path)
        photometry_path = get_photometry_path(self.objectid, base_path)

        source_path.parent.mkdir(parents=True, exist_ok=True)
        crossmatch_path.parent.mkdir(parents=True, exist_ok=True)
        photometry_path.parent.mkdir(parents=True, exist_ok=True)

        # source metadata row
        meta = {
            k: v
            for k, v in self.model_dump(
                exclude_defaults=True, exclude_computed_fields=True
            ).items()
            if k not in ["photometry", "crossmatches"]
        }

        pd.DataFrame([meta]).to_parquet(source_path, compression="zstd")

        # Dump crossmatches to json
        crossmatch_path.write_text(json.dumps(self.crossmatches))

        # photometry
        df = (
            self.get_detections(min_snr=3.0)
            if trim_photometry
            else self.get_photometry()
        )

        # Clip derived columns
        df = df[list(Observation.model_fields.keys())]

        df.to_parquet(photometry_path, compression="zstd")

    @classmethod
    def from_parquet(
        cls, object_id: str, base_path: Path | str | None = None
    ) -> "Source":
        """
        Load a Source object from parquet files.

        :param object_id: Object ID
        :param base_path: Base path to parquet files
        :return: Source object
        """
        meta = pd.read_parquet(get_source_path(object_id, base_path))
        photometry_df = pd.read_parquet(get_photometry_path(object_id, base_path))
        crossmatches = json.loads(get_crossmatch_path(object_id, base_path).read_text())

        photometry = [
            Observation(**row) for row in photometry_df.to_dict(orient="records")
        ]

        return cls(
            **meta.iloc[0].to_dict(), photometry=photometry, crossmatches=crossmatches
        )

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
