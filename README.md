# pyro-scrapper

## Overview

## Contributing

Please refer to [`CONTRIBUTING`](CONTRIBUTING.md) if you wish to contribute to this project.

## Exporting requirements

We use Poetry with the export plugin (already configured in `pyproject.toml`). To generate requirement files:

- Runtime deps: `poetry export -f requirements.txt --without-hashes --output requirements.txt`
- Quality tools: `poetry export -f requirements.txt --without-hashes --only quality --output requirements-quality.txt`
- Dev/test deps: `poetry export -f requirements.txt --without-hashes --with dev --output requirements-dev.txt`

## Running quality checks

Copy/paste to match the CI style job (uses `uv` in a local venv):

```bash
# create or reuse .venv on Python 3.11 (matches CI)
uv python install 3.11
uv venv --python 3.11 .venv
source .venv/bin/activate

# export and install quality deps
poetry export -f requirements.txt --without-hashes --only quality --output requirements-quality.txt
uv pip install -r requirements-quality.txt

# run the checks
ruff format --check --diff .
ruff check --diff .
```

For mypy (same deps as CI):

```bash
poetry export -f requirements.txt --without-hashes --with quality --output requirements-quality.txt
uv pip install -r requirements-quality.txt
mypy
```

## Credits

This project is developed and maintained by the repo owner and volunteers from [Pyronear](https://pyronear.org/).

## License

Distributed under the Apache 2 License. See [`LICENSE`](LICENSE) for more information.
