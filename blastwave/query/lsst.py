"""
LSST Client
"""

from babamul.models import LsstAlert

from blastwave.query.alert import AlertClient


class LSSTClient(AlertClient):
    """
    LSST Client
    """

    base_catalog = "LSST"
    base_model = LsstAlert
