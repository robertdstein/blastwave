"""
Client for querying BOOM
"""

import logging
import os
import threading
from functools import partial
from typing import Callable, Iterable, Mapping, Optional, Sequence, TypeVar
from urllib.parse import urljoin

import numpy as np
import requests
from dotenv import load_dotenv
from typing_extensions import deprecated
from urllib3.util import Retry

from blastwave.errors import BOOMCredentialsError
from blastwave.models.query import BOOMQuery, CatalogQuery, FilterQuery
from blastwave.query.parallel import (
    DEFAULT_N_THREADS,
    run_parallel_funcs,
    tolerate_errors,
)
from blastwave.query.timeout import DEFAULT_TIMEOUT, TimeoutHTTPAdapter

logger = logging.getLogger(__name__)

BASE_URL = "https://api.kaboom.caltech.edu"
BOOM_POOL_MAXSIZE = 32

R = TypeVar("R")


class BOOMClient:
    """
    Basic BOOM client class for executing functions

    :param base_url: Base URL to query (default: https://api.kaboom.caltech.edu)
    :param n_threads: Default number of threads to use for batch queries.
        Use one to run batch queries serially.
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        n_threads: int = DEFAULT_N_THREADS,
    ):
        self.base_url = base_url
        self.n_threads = self.validate_n_threads(n_threads)
        self._session: None | requests.Session = None
        self._session_headers: None | dict = None
        self._catalogs: None | list[str] = None
        # So that parallel queries do not each request their own token
        self._lock = threading.RLock()
        # Never more requests in flight than the connection pool can hold
        self._request_semaphore = threading.BoundedSemaphore(BOOM_POOL_MAXSIZE)

    @staticmethod
    def validate_n_threads(n_threads: int) -> int:
        """
        Check that a thread count is sane, capping it at the connection pool size.

        :param n_threads: Requested number of threads
        :return: Number of threads to actually use
        """
        if n_threads < 1:
            raise ValueError(f"n_threads must be at least one, got {n_threads}")
        if n_threads > BOOM_POOL_MAXSIZE:
            logger.warning(
                f"n_threads of {n_threads} exceeds the connection pool size of "
                f"{BOOM_POOL_MAXSIZE}, so using {BOOM_POOL_MAXSIZE} threads instead."
            )
            return BOOM_POOL_MAXSIZE
        return n_threads

    def _resolve_n_threads(self, n_threads: int | None = None) -> int:
        """
        Resolve a thread count, falling back to the client default.

        :param n_threads: Requested number of threads
        :return: Number of threads to actually use
        """
        if n_threads is None:
            return self.n_threads
        return self.validate_n_threads(n_threads)

    @property
    def catalog(self) -> str | None:
        """Functions as a default catalog name for queries."""
        return None

    @staticmethod
    def set_up_session() -> requests.Session:
        """
        Set up a session for sending requests to BOOM.

        :return: Session
        """
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "POST", "PATCH"],
        )
        adapter = TimeoutHTTPAdapter(
            max_retries=retries, pool_maxsize=BOOM_POOL_MAXSIZE
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def get_session_headers(self) -> dict:
        """
        Get session headers

        :return: Session headers
        """
        if self._session_headers is None:
            with self._lock:
                if self._session_headers is None:
                    self._session_headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._get_boom_token()}",
                    }
        assert self._session_headers is not None
        return self._session_headers

    def get_session(self) -> requests.Session:
        """
        Wrapper for getting the session.
        If the session is not set up, it will be set up.

        :return: Session
        """
        if self._session is None:
            with self._lock:
                if self._session is None:
                    self._session = self.set_up_session()
        assert self._session is not None
        return self._session

    def _get_boom_token(self) -> str:
        """
        Get Boom token from environment variable.

        :return: Boom token
        """
        load_dotenv()

        user = os.getenv("BOOM_API_USER")

        if user is None:
            err = (
                "No Boom API user specified. "
                "Add this to .env or set BOOM_API_USER environment variable."
            )
            logger.error(err)
            raise BOOMCredentialsError(err)

        password = os.getenv("BOOM_API_PASSWORD")

        if password is None:
            err = (
                "No Boom API password specified. "
                "Add this to .env or set BOOM_API_PASSWORD environment variable."
            )
            logger.error(err)
            raise BOOMCredentialsError(err)

        boom_token = self.get_fresh_token(user, password)
        return boom_token

    def api(
        self, method: str, endpoint: str, data: Optional[Mapping] = None
    ) -> requests.Response:
        """
        Make an API call to a BOOM instance

        headers = {'Authorization': f'token {self.token}'}
        response = requests.request(method, endpoint, json_dict=data, headers=headers)

        :param method: HTTP method
        :param endpoint: API endpoint
        :param data: JSON data to send
        :return: response from API call
        """
        method = method.lower()

        session = self.get_session()
        headers = self.get_session_headers()

        methods: dict[str, Callable[..., requests.Response]] = {
            "head": session.head,
            "get": session.get,
            "post": session.post,
            "put": session.put,
            "patch": session.patch,
            "delete": session.delete,
        }

        if endpoint is None:
            raise ValueError("Endpoint not specified")
        if method not in ["head", "get", "post", "put", "patch", "delete"]:
            raise ValueError(f"Unsupported method: {method}")

        url = urljoin(self.base_url, endpoint)

        with self._request_semaphore:
            if method == "get":
                response = methods[method](
                    url,
                    params=data,
                    headers=headers,
                )
            else:
                response = methods[method](
                    url,
                    json=data,
                    headers=headers,
                )

        return response

    def query(self, query: BOOMQuery | dict) -> list[dict]:
        """
        Make a find query call

        :param query: Query to execute
        :return: List of results
        """
        boom_query = BOOMQuery.model_validate(query)
        res = self.api(
            "post", "queries/find", data=boom_query.model_dump(exclude_none=True)
        )
        res.raise_for_status()
        return res.json()["data"]

    def count(self, query: CatalogQuery | FilterQuery | BOOMQuery | dict) -> int:
        """
        Make a count call

        :param query: Query to count
        :return: Number of records
        """
        boom_query = FilterQuery.model_validate(query)
        res = self.api("post", "queries/count", data=boom_query.model_dump())
        res.raise_for_status()
        return res.json()["data"]

    def run_batch(
        self,
        tasks: Sequence[Callable[[], R]],
        desc: str,
        n_threads: int | None = None,
        progress: bool = False,
        skip_errors: bool = False,
    ) -> list[R | None]:
        """
        Run a set of prepared client calls in parallel, using a pool of threads.

        :param tasks: Calls to run, as zero-argument functions
        :param desc: Label for the batch, used for the progress bar
        :param n_threads: Number of threads to use (default: client n_threads)
        :param progress: Whether to show a progress bar
        :param skip_errors: Whether to log and skip failed tasks, returning
            None in their place, rather than raising the error
        :return: List of results, one entry per task, in the order of the tasks
        """
        funcs: list[Callable[[], R | None]] = (
            [tolerate_errors(task) for task in tasks] if skip_errors else list(tasks)
        )
        return run_parallel_funcs(
            funcs,
            n_threads=self._resolve_n_threads(n_threads),
            progress=progress,
            desc=desc,
        )

    def batch_query(
        self,
        queries: Iterable[BOOMQuery | dict],
        n_threads: int | None = None,
        progress: bool = False,
        skip_errors: bool = False,
    ) -> list[list[dict] | None]:
        """
        Make find query calls for a set of queries, running them in parallel.

        :param queries: Queries to execute
        :param n_threads: Number of threads to use (default: client n_threads)
        :param progress: Whether to show a progress bar
        :param skip_errors: Whether to log and skip failed queries, returning
            None in their place, rather than raising the error
        :return: List of results, one entry per query, in the order of the queries
        """
        tasks = [partial(self.query, query) for query in queries]
        return self.run_batch(tasks, "Queries", n_threads, progress, skip_errors)

    def batch_count(
        self,
        queries: Iterable[CatalogQuery | FilterQuery | BOOMQuery | dict],
        n_threads: int | None = None,
        progress: bool = False,
        skip_errors: bool = False,
    ) -> list[int | None]:
        """
        Make count calls for a set of queries, running them in parallel.

        :param queries: Queries to count
        :param n_threads: Number of threads to use (default: client n_threads)
        :param progress: Whether to show a progress bar
        :param skip_errors: Whether to log and skip failed queries, returning
            None in their place, rather than raising the error
        :return: List of counts, one entry per query, in the order of the queries
        """
        tasks = [partial(self.count, query) for query in queries]
        return self.run_batch(tasks, "Counts", n_threads, progress, skip_errors)

    def get_fresh_token(self, username: str, password: str) -> str:
        """
        Get a fresh token from the Boom API.

        :param username: Username for Boom API
        :param password: Password for Boom API
        :return: New token from Boom API
        """
        response = requests.post(
            urljoin(self.base_url, "auth"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"username": username, "password": password},
            timeout=DEFAULT_TIMEOUT,
        )

        if response.status_code != 200:
            logger.error(f"Failed to get new token: {response.text}")
            raise BOOMCredentialsError(f"Failed to get new token: {response.text}")

        return response.json()["access_token"]

    def ping(self) -> requests.Response:
        """
        Make a ping call

        :return: Response from ping call
        """
        return self.api("get", "")

    def get_catalogs(self) -> list[str]:
        """
        Get a list of catalogs available in BOOM

        :return: List of catalogs
        """
        if self._catalogs is None:
            with self._lock:
                if self._catalogs is None:
                    res = self.api("get", "catalogs")
                    res.raise_for_status()
                    self._catalogs = [x["name"] for x in res.json()["data"]]

        assert self._catalogs is not None
        return self._catalogs

    def resolve_catalog(self, catalog: str | None = None) -> str:
        """
        Resolve a catalog name

        :param catalog: Catalog name
        :return: Catalog name to use in query
        """
        name = catalog or self.catalog
        if name is None:
            raise ValueError("No catalog specified")
        return name

    def get_entry_count(self, catalog: str | None = None) -> int:
        """
        Get the number of entries in a catalog

        :param catalog: Catalog name
        :return: Number of entries in catalog
        """
        query = CatalogQuery(catalog_name=self.resolve_catalog(catalog))
        res = self.api(
            "post",
            "queries/estimated_count",
            data=query.model_dump(exclude_none=True),
        )
        res.raise_for_status()
        return res.json()["data"]

    def get_catalog_indexes(self, catalog: str | None = None) -> int:
        """
        Get the indexes columns for a catalog

        :param catalog: Catalog name
        :return: Example json
        """
        res = self.api("get", f"/catalogs/{self.resolve_catalog(catalog)}/indexes")
        res.raise_for_status()
        return res.json()["data"]

    def get_sample_data(self, catalog: str | None = None) -> dict:
        """
        Get a sample data entry from a catalog

        :param catalog: Catalog name
        :return: Example json
        """
        res = self.api("get", f"/catalogs/{self.resolve_catalog(catalog)}/sample")
        res.raise_for_status()
        return res.json()["data"][0]

    @staticmethod
    def get_near_sphere_dist(radius_arcsec: float) -> float:
        """
        Convert a radius in arcseconds to a radius
        in meters (on Earth surface) for use in a $nearSphere query

        :param radius_arcsec: Radius in arcseconds
        :return: Radius in meters
        """
        return ((radius_arcsec / 3600.0) * np.pi / 180.0) * 6371008.8

    def cone_search(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        ra: float,
        dec: float,
        radius_arcsec: float = 1.0,
        catalog: str | None = None,
        limit: int | None = 1,
        filter_query: FilterQuery | dict | None = None,
        projection: dict | None = None,
    ) -> list[dict]:
        """
        Function to do a cone search

        :param ra: Ra (decimal degrees)
        :param dec: Declination (decimal degrees)
        :param radius_arcsec: Search radius (arcsec)
        :param catalog: Catalog name
        :param limit: Number of results to return
        :param filter_query: Optional filter to use instead of constructing one
        :param projection: Optional projection to use instead of constructing one
        :return: List of search results (possibly of length 0 if there are no results)
        """

        base_filter = {
            "coordinates.radec_geojson": {
                "$nearSphere": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [ra - 180.0, dec],
                    },
                    "$maxDistance": self.get_near_sphere_dist(radius_arcsec),
                }
            }
        }

        if filter_query is not None:
            if isinstance(filter_query, dict):
                filter_query = FilterQuery(
                    catalog_name=self.resolve_catalog(catalog), filter=filter_query
                )

            assert filter_query.catalog_name == self.resolve_catalog(
                catalog
            ), "Mismatched catalog names in query and function argument"

            base_filter.update(filter_query.filter or {})

        res = self.query(
            BOOMQuery(
                catalog_name=self.resolve_catalog(catalog),
                filter=base_filter,
                limit=limit,
                projection=projection,
            )
        )
        return res

    def batch_cone_search(
        self,
        coordinates: Iterable[Sequence[float]],
        n_threads: int | None = None,
        progress: bool = False,
        skip_errors: bool = False,
        **kwargs,
    ) -> list[list[dict] | None]:
        """
        Do a set of cone searches, running them in parallel.

        :param coordinates: Positions to search, as (ra, dec) pairs in decimal degrees
        :param n_threads: Number of threads to use (default: client n_threads)
        :param progress: Whether to show a progress bar
        :param skip_errors: Whether to log and skip failed searches, returning
            None in their place, rather than raising the error
        :param kwargs: Arguments for each search, passed to cone_search, i.e
            radius_arcsec, catalog, limit, filter_query and projection
        :return: List of search results, one entry per position,
            in the order of the positions
        """
        tasks = [
            partial(self.cone_search, float(ra), float(dec), **kwargs)
            for ra, dec in coordinates
        ]
        return self.run_batch(tasks, "Cone searches", n_threads, progress, skip_errors)


@deprecated("Use BOOMClient instead")
class BoomClient(BOOMClient):
    """
    Deprecated class for BOOM client. Use BOOMClient instead.
    """
