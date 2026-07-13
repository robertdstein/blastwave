"""
ZTF Client
"""

from babamul.models import ZtfAlert

from blastwave.query.alert import AlertClient


class ZTFClient(AlertClient):
    """
    ZTF Client
    """

    base_catalog = "ZTF"
    base_model = ZtfAlert
