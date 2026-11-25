"""
blastwave is a python client for querying Boom
"""

from blastwave.errors import SKIPPABLE_ERRORS, BOOMCredentialsError
from blastwave.models import BOOMQuery, CatalogQuery, FilterQuery, Observation, Source
from blastwave.query import (
    BOOM_POOL_MAXSIZE,
    DEFAULT_N_THREADS,
    BOOMClient,
    LSSTClient,
    ZTFClient,
    run_parallel,
)
from blastwave.utils import (
    get_crossmatch_path,
    get_data_dir,
    get_photometry_path,
    get_source_path,
)
