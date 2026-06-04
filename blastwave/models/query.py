"""
Model for BOOM queries
"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel


class CatalogQuery(BaseModel):
    """
    Model for BOOM queries using only catalog name
    """

    catalog_name: str

    model_config = {"from_attributes": True}


class FilterQuery(CatalogQuery):
    """
    Model for BOOM queries using catalog name and a filter
    """

    filter: Mapping[str, Any] | None = None


class BOOMQuery(FilterQuery):
    """
    Model for a full BOOM query
    """

    limit: int | None = None
    max_time_ms: int | None = None
    projection: Mapping[str, Any] | None = None
    skip: int | None = None
    sort: Mapping[str, Any] | None = None
