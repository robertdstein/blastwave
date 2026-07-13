"""
Functions to create a combined source path
"""

from pathlib import Path

import pandas as pd

from blastwave.utils.cache import get_consolidated_source_path, get_source_dir


def combine_sources(
    data_dir: Path | str | None = None,
):
    """
    Combines sources into a single parquet file

    :param data_dir: Directory where combined sources are stored
    :return: None
    """
    df = pd.read_parquet(get_source_dir(data_dir))
    df.to_parquet(get_consolidated_source_path(data_dir), compression="zstd")


def load_consolidated_sources(
    data_dir: Path | str | None = None,
) -> pd.DataFrame:
    """
    Loads consolidated sources from a single parquet file

    :param data_dir: Directory where consolidated sources are stored
    :return: Dataframe with consolidated sources
    """
    consolidated_sources = get_consolidated_source_path(data_dir)
    return pd.read_parquet(consolidated_sources)
