"""
Observation model
"""

import logging

import numpy as np
import pandas as pd
from pydantic import BaseModel, computed_field

logger = logging.getLogger(__name__)


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
    psf_flux: float
    psf_flux_err: float

    @computed_field()
    @property
    def isdiffpos(self) -> bool:
        """
        Determine if the observation is a positive detection

        :return: True if positive detection, False otherwise
        """
        return (self.psf_flux > 0.0) & (pd.notnull(self.magpsf))

    @computed_field()
    @property
    def altdiffmaglim(self) -> float:
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
