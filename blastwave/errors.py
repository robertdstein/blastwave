"""
Custom Exceptions for blastwave
"""

import requests
from pydantic import ValidationError


class BOOMCredentialsError(Exception):
    """
    Exception raised when no credentials are provided.
    """


# Errors from a query itself, which a batch can skip; anything else raises
SKIPPABLE_ERRORS = (
    requests.RequestException,
    KeyError,
    IndexError,
    ValidationError,
)
