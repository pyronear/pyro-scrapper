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

1) Export quality deps:  
   `poetry export -f requirements.txt --without-hashes --only quality --output requirements-quality.txt`  
2) Install them in your venv: `python -m pip install -r requirements-quality.txt`  
3) Auto-fix lint/format: `make style`  
4) Full check (lint + mypy): `make quality`

## Credits

This project is developed and maintained by the repo owner and volunteers from [Pyronear](https://pyronear.org/).

## License

Distributed under the Apache 2 License. See [`LICENSE`](LICENSE) for more information.
