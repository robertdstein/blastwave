"""
Custom Exceptions for blastwave
"""

import requests
from pydantic import ValidationError


class BOOMCredentialsError(Exception):
    """
    Exception raised when no credentials are provided.
    """


# Errors which affect one query alone, so a batch can skip them and carry on.
# Anything else is wrong with the whole batch, and raises rather than repeating.
SKIPPABLE_ERRORS = (
    requests.RequestException,
    KeyError,
    IndexError,
    ValidationError,
)
