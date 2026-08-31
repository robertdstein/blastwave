"""
Tests for TimeoutHTTPAdapter
"""

# pylint: disable=missing-function-docstring

import unittest
from unittest import mock

from requests import PreparedRequest
from requests.adapters import HTTPAdapter

from blastwave.query.timeout import DEFAULT_TIMEOUT, TimeoutHTTPAdapter


class TestTimeoutHTTPAdapter(unittest.TestCase):
    """
    Tests for TimeoutHTTPAdapter
    """

    def test_default_timeout(self):
        adapter = TimeoutHTTPAdapter()
        self.assertEqual(adapter.timeout, DEFAULT_TIMEOUT)

    def test_custom_timeout(self):
        adapter = TimeoutHTTPAdapter(timeout=5)
        self.assertEqual(adapter.timeout, 5)

    def test_timeout_kwarg_not_passed_to_super_init(self):
        # If "timeout" leaked into HTTPAdapter.__init__ it would raise
        # a TypeError, since HTTPAdapter doesn't accept that kwarg.
        try:
            TimeoutHTTPAdapter(timeout=5, pool_maxsize=4)
        except TypeError as exc:
            self.fail(f"Unexpected TypeError: {exc}")

    def test_send_uses_default_timeout_when_unset(self):
        adapter = TimeoutHTTPAdapter()
        request = PreparedRequest()
        request.prepare(method="GET", url="https://example.com")

        with mock.patch.object(HTTPAdapter, "send") as mock_send:
            adapter.send(request)

        _, kwargs = mock_send.call_args
        self.assertEqual(kwargs["timeout"], DEFAULT_TIMEOUT)

    def test_send_respects_explicit_timeout(self):
        adapter = TimeoutHTTPAdapter()
        request = PreparedRequest()
        request.prepare(method="GET", url="https://example.com")

        with mock.patch.object(HTTPAdapter, "send") as mock_send:
            adapter.send(request, timeout=1)

        _, kwargs = mock_send.call_args
        self.assertEqual(kwargs["timeout"], 1)


if __name__ == "__main__":
    unittest.main()
