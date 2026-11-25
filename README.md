# blastwave

[![Coverage Status](https://coveralls.io/repos/github/robertdstein/blastwave/badge.svg?branch=tests)](https://coveralls.io/github/robertdstein/blastwave?branch=tests)
[![CI](https://github.com/robertdstein/blastwave/actions/workflows/continuous_integration.yml/badge.svg)](https://github.com/robertdstein/blastwave/actions/workflows/continuous_integration.yml) 
[![PyPI version](https://badge.fury.io/py/blastwave.svg)](https://badge.fury.io/py/blastwave)


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

# Parallel queries

Queries spend nearly all of their time waiting on the API, so each client can
run a set of them at once in a pool of threads, rather than one after another:

```python
from blastwave import ZTFClient

client = ZTFClient()

# One source at a time
sources = [client.get_source(x) for x in object_ids]

# All of them at once
sources = client.batch_get_source(object_ids, progress=True)
```

The batch methods are `batch_query`, `batch_count`, `batch_cone_search`,
`batch_get_full_data` and `batch_get_source`. Each returns one entry per input,
in the order of the inputs, and takes:

* `n_threads`, to override the client default (set with `ZTFClient(n_threads=16)`)
* `progress`, to show a progress bar
* `skip_errors`, to log and skip any failed entries, returning `None` in their
  place, rather than raising the error

Single queries are also faster, because each client now fetches the alert and
aux data for a source at the same time, and likewise its crossmatches and the
photometry of each crossmatched survey.

To run everything serially again, use a single thread:

```python
client = ZTFClient(n_threads=1)
```
