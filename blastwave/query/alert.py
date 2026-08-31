"""
Base Class for an Alert Survey Client
"""

from abc import ABC, abstractmethod
from typing import Callable

import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord
from babamul.models import LsstAlert, ZtfAlert

from blastwave.models import BOOMQuery, Source
from blastwave.projections import lsst_aux_projection, ztf_aux_projection
from blastwave.query.boom import BoomClient
from blastwave.utils.photometry import (
    deduplicate_lsst_photometry,
    deduplicate_ztf_photometry,
)

parse_map = {
    "ZTF_alerts": deduplicate_ztf_photometry,
    "LSST_alerts": deduplicate_lsst_photometry,
}

trim_projection_map = {
    "ZTF_alerts": ztf_aux_projection,
    "LSST_alerts": lsst_aux_projection,
}

GenerateFunc = Callable[[dict, pd.DataFrame], Source]
generator_mapping: dict[str, GenerateFunc] = {
    "ZTF_alerts": Source.from_ztf,
    "LSST_alerts": Source.from_lsst,
}


class AlertClient(BoomClient, ABC):
    """
    Base class for Alert Survey Client
    """

    @property
    @abstractmethod
    def base_catalog(self) -> str:
        """The BOOM catalog name for this survey."""

    @property
    @abstractmethod
    def base_model(self) -> type[LsstAlert] | type[ZtfAlert]:
        """The Babamul model for this survey."""

    @property
    def catalog(self) -> str:
        """
        The BOOM catalog name for this survey.
        """
        return f"{self.base_catalog}_alerts"

    @property
    def aux_table(self) -> str:
        """
        The BOOM aux catalog name for this survey.

        :return: Name of the BOOM aux catalog
        """
        return f"{self.catalog}_aux"

    def get_latest_alert(
        self,
        object_id: str | int,
        catalog: str | None = None,
        projection: dict | None = None,
    ) -> dict:
        """
        Get latest alert for a given object.

        :param object_id: Object ID
        :param catalog: Catalog name (e.g. ZTF_alerts or LSST_alerts)
        :param projection: Mongodb projection for fields to return
        :return: Nested dictionary of the latest alert for the given object ID
        """
        catalog = catalog or self.catalog
        query = BOOMQuery(
            catalog_name=catalog,
            filter={"objectId": {"$eq": str(object_id)}},
            limit=1,
            projection=projection,
            sort={"candidate.jd": -1},
        )
        return self.query(query)[0]

    def get_aux_data(
        self,
        object_id: str | int,
        catalog: str | None = None,
        projection: dict | None = None,
        trim: bool = True,
    ) -> dict:
        """
        Get aux data for a given object.

        :param object_id: Object ID
        :param catalog: Parent catalog name (e.g. ZTF_alerts or LSST_alerts)
        :param projection: Projection for fields to return
        :param trim: Whether to trim the data
        :return: Dictionary of the aux data for the given object ID
        """

        aux_table = f"{catalog}_aux" if catalog is not None else self.aux_table

        if trim & (projection is None):
            projection = trim_projection_map[aux_table.replace("_aux", "")]

        query = BOOMQuery(
            catalog_name=aux_table,
            filter={"_id": {"$eq": str(object_id)}},
            projection=projection,
        )
        return self.query(query)[0]

    def get_full_data(
        self,
        object_id: str | int,
        catalog: str | None = None,
        alert_projection: dict | None = None,
        aux_projection: dict | None = None,
        trim: bool = False,
    ) -> dict:
        """
        Get full data for a given object, combining the latest alert and aux data.

        :param object_id: Object ID
        :param catalog: Parent catalog name (e.g. ZTF_alerts or LSST_alerts)
        :param alert_projection: Projection for fields to return for alert
        :param aux_projection: Projection for fields to return for aux data
        :param trim: Whether to trim the data
        :return: Dictionary of the aux data for the given object ID
        """
        latest = self.get_latest_alert(
            object_id, catalog=catalog, projection=alert_projection
        )
        aux_data = self.get_aux_data(
            object_id, catalog=catalog, projection=aux_projection, trim=trim
        )
        aux_data.update(latest)
        aux_data = self.update_crossmatches(aux_data)
        return aux_data

    def update_crossmatches(self, aux_data: dict) -> dict:
        """
        Update the cross-matches in the aux data to include the latest alert data.

        :param aux_data: Dictionary of aux data
        :return: Updated aux data with cross-matches
        """

        if not "cross_matches" in aux_data:
            aux_data["cross_matches"] = {}

        aux_data["cross_matches"] = {
            k: v for k, v in aux_data["cross_matches"].items() if k != ""
        }

        src_position = SkyCoord(
            aux_data["candidate"]["ra"], aux_data["candidate"]["dec"], unit="deg"
        )

        for cat in ["LSPSC", "NED", "PS1_DR2"]:
            matches = self.cone_search(
                src_position.ra.deg, src_position.dec.deg, catalog=cat, limit=1
            )

            # Should be zero or 1 for now
            for match in matches:
                pos = match.pop("coordinates")["radec_geojson"]
                sep = float(
                    src_position.separation(
                        SkyCoord(
                            pos["coordinates"][0] + 180.0,
                            pos["coordinates"][1],
                            unit="deg",
                        )
                    ).arcsec
                )
                match["distance_arcsec"] = sep

            aux_data["cross_matches"][cat] = matches
        return aux_data

    def get_match_photometry(self, catalog: str, aliases: dict) -> pd.DataFrame:
        """
        Get photometry for a given survey.

        :param catalog: Catalog name
        :param aliases: Dictionary of aliases
        :return: DataFrame of photometry for the survey
        """
        parse_f = parse_map[catalog]
        survey = catalog.split("_")[0]
        try:
            match_name = aliases[survey][0]
            match = self.get_full_data(match_name, catalog=catalog)
            photometry = parse_f(match)
            new_df = pd.DataFrame(photometry)
            new_df["survey"] = survey
        except (KeyError, IndexError):
            new_df = pd.DataFrame()
        return new_df

    def get_all_match_photometry(self, aliases: dict) -> pd.DataFrame:
        """
        Get photometry for all cross-matched surveys.

        :param aliases: Aliases
        :return: DataFrame of photometry for all cross-matched surveys
        """
        all_match_photometry = []
        for survey in parse_map:
            all_match_photometry.append(self.get_match_photometry(survey, aliases))
        return pd.concat(all_match_photometry, ignore_index=True)

    def get_all_photometry(
        self, full_alert: dict, catalog: str | None = None
    ) -> pd.DataFrame:
        """
        Get photometry for the base survey and all cross-matched surveys.

        :param full_alert: Full alert from get_full_data
        :param catalog: Catalog name
        :return: DataFrame of photometry for all cross-matched surveys
        """
        catalog = self.resolve_catalog(catalog)
        parse_f = parse_map[catalog]
        photometry_df = parse_f(full_alert)
        photometry_df["survey"] = catalog.split("_")[0]

        if "aliases" in full_alert:
            match_photometry = self.get_all_match_photometry(full_alert["aliases"])
            if len(match_photometry) > 0:
                photometry_df = pd.concat(
                    [photometry_df, match_photometry], ignore_index=True
                )

        photometry_df = (
            photometry_df.sort_values(by="jd").reset_index(drop=True)
        ).replace({None: np.nan})
        return photometry_df

    def get_source(
        self,
        object_id: str | int,
        catalog: str | None = None,
        alert_projection: dict | None = None,
        aux_projection: dict | None = None,
    ) -> Source:
        """
        Get the full source data for a given object ID.

        :param object_id: Object ID
        :param catalog: Catalog name
        :param alert_projection: Projection for fields to return for alert
        :param aux_projection: Projection for fields to return for aux data
        :return: Dictionary of source data
        """
        catalog = self.resolve_catalog(catalog)
        full_data = self.get_full_data(
            object_id,
            catalog=catalog,
            alert_projection=alert_projection,
            aux_projection=aux_projection,
        )
        photometry_df = self.get_all_photometry(full_data, catalog=catalog)
        return generator_mapping[catalog](full_data, photometry_df)
