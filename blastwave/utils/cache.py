"""
Scripts for handling cache paths
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_data_dir(data_dir: Path | str | None = None) -> Path:
    """
    Get path to data directory

    :param data_dir: Path to data directory
    :return: Path to default data directory
    """
    _data_dir = data_dir or os.getenv("BLASTWAVE_DATA_DIR")
    if _data_dir is None:
        raise ValueError("'BLASTWAVE_DATA_DIR' environment variable not set")
    return Path(_data_dir)


def get_crossmatch_dir(data_dir: Path | str | None = None) -> Path:
    """
    Get path to crossmatch directory

    :param data_dir: Path to data directory
    :return: Path to crossmatch directory
    """
    return get_data_dir(data_dir) / "crossmatches"


def get_crossmatch_path(
    object_id: str | int, data_dir: Path | str | None = None
) -> Path:
    """
    Get path to crossmatch file

    :param object_id: Object ID
    :param data_dir: Data directory
    :return: Path to crossmatch file
    """
    return get_crossmatch_dir(data_dir) / f"{object_id}.json"


def get_source_dir(data_dir: Path | str | None = None) -> Path:
    """
    Get path to source directory

    :param data_dir: Path to data directory
    :return: Path to source directory
    """
    return get_data_dir(data_dir) / "sources"


def get_source_path(object_id: str | int, data_dir: Path | str | None = None) -> Path:
    """
    Get path to source file

    :param object_id: Object ID
    :param data_dir: Data directory
    :return: Path to source file
    """
    return get_source_dir(data_dir) / f"{object_id}.parquet"


def get_consolidated_source_path(data_dir: Path | str | None = None) -> Path:
    """
    Get path to consolidated source file

    :param data_dir: Path to data directory
    :return: Path to consolidated source file
    """
    return get_data_dir(data_dir) / "consolidated_source.parquet"


def get_photometry_dir(data_dir: Path | str | None = None) -> Path:
    """
    Get path to photometry directory

    :param data_dir: Path to data directory
    :return: Path to photometry directory
    """
    return get_data_dir(data_dir) / "photometry"


def get_photometry_path(
    object_id: str | int, data_dir: Path | str | None = None
) -> Path:
    """
    Get path to photometry directory

    :param object_id: Object ID
    :param data_dir: Data directory
    :return: Path to photometry file
    """
    return get_photometry_dir(data_dir) / f"{object_id}.parquet"
