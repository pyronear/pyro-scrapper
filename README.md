# pyro-scrapper

## Overview

## Local setup with uv

Use uv (0.5.13 in CI) with Python 3.11 to mirror `.github/workflows/style.yml`.

```bash
# create and activate a virtual environment
uv venv --python 3.11 .venv
source .venv/bin/activate

# install Poetry + export plugin with uv so we can reuse the CI export step
uv pip install "poetry==2.0.0" poetry-plugin-export

# sync all dependencies (app + dev + quality groups)
poetry export -f requirements.txt --without-hashes --with dev,quality --output requirements-dev.txt
uv pip sync requirements-dev.txt
```

## Run style checks locally

The following commands reproduce the quality jobs defined in `.github/workflows/style.yml`:

```bash
ruff format --check --diff .
ruff check --diff .
mypy
```

## Contributing

Please refer to [`CONTRIBUTING`](CONTRIBUTING.md) if you wish to contribute to this project.

## Credits

This project is developed and maintained by the repo owner and volunteers from [Pyronear](https://pyronear.org/).

## License

Distributed under the Apache 2 License. See [`LICENSE`](LICENSE) for more information.
