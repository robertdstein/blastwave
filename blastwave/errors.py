"""
Custom Exceptions for blastwave
"""

import requests
from pydantic import ValidationError


class BOOMCredentialsError(Exception):
    """
    Exception raised when no credentials are provided.
    """


# Errors which affect one query alone: the API or network failed for it, or the
# data it asked for is missing or malformed. A batch can skip these and carry
# on. Anything else, such as missing credentials or a bad argument, is a problem
# with the batch as a whole, and is raised rather than repeated for every entry.
SKIPPABLE_ERRORS = (
    requests.RequestException,
    KeyError,
    IndexError,
    ValidationError,
)
