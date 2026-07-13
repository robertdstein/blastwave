# blastwave

Python client for BOOM queries, similar to [penquins](https://github.com/dmitryduev/penquins).

# Installation

# Install blastwave with pip:

The simplest way to install blastwave is via pip:

```bash
pip install blastwave
```

or, if you want to edit the code yourself:

```bash
git clone git@github.com:robertdstein/blastwave.git
cd blastwave
pip install -e ".[dev]"
```

# Credentials

Set your credentials in the environment:

```bash
export BOOM_USERNAME="your_username"
export BOOM_PASSWORD="your_password"
```

or by copying the `.env.example` file to `.env` and filling in your credentials there.

If you want to use the parquet cache, you should also set this in the same way via env:

```bash
export BLASTWAVE_DATA_DIR="/path/to/cache/dir"
```

# Usage

See example Jupyter notebooks for usage examples.
