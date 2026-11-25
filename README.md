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

Queries spend nearly all of their time waiting on the API, so use a batch method
to send a set of them at once from a pool of threads:

```python
from blastwave import ZTFClient

client = ZTFClient()
sources = client.batch_get_source(object_ids, progress=True)
```

The batch methods are `batch_query`, `batch_count`, `batch_cone_search`,
`batch_get_full_data` and `batch_get_source`. Each one returns a list with one
entry per input, in the order of the inputs, and takes:

* `n_threads`, the number of threads to use for this call
* `progress`, to show a progress bar
* `skip_errors`, to log and skip any failed entry, returning `None` in its place
  instead of raising the error

Pick the thread count for a client when you create it, up to a limit of 32:

```python
client = ZTFClient(n_threads=16)
```

A single thread sends the queries one at a time:

```python
client = ZTFClient(n_threads=1)
```

Each `get_source` call uses the pool as well, since it fetches the alert and aux
data for the source together, and likewise the crossmatches and the photometry
of each crossmatched survey. Allow for that when choosing a thread count: a
`batch_get_source` of 16 threads has considerably more than 16 queries in
flight.
