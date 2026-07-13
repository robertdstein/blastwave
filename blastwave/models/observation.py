"""
Observation model
"""

import logging
from typing import Literal

import numpy as np
import pyarrow as pa
from pydantic import BaseModel, computed_field

from blastwave.models.parquet import pydantic_to_arrow_schema

logger = logging.getLogger(__name__)

ObsClass = Literal["alert", "fp", "ul"]


class Observation(BaseModel):
    """
    Model for an observation
    """

    jd: float
    magpsf: float
    sigmapsf: float
    diffmaglim: float
    ra: float | None
    dec: float | None
    snr: float
    band: str
    survey: str
    det_type: ObsClass = "alert"
    isdiffpos: bool

    @computed_field()
    @property
    def estdiffmaglim(self) -> float:
        """
        Estimate the difference magnitude limit based on snr and magpsf

        :return:
        """
        return self.magpsf - 2.5 * float(np.log10(5.0 / self.snr))

    @computed_field()
    @property
    def mjd(self) -> float:
        """
        Convert JD to MJD
        """
        return self.jd - 2400000.5

    @classmethod
    def get_arrow_schema(cls) -> pa.Schema:
        """
        Get arrow schema from pydantic model

        :return: Arrow schema
        """
        return pydantic_to_arrow_schema(cls)
