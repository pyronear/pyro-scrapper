# This target runs checks on all files
quality:
	ruff format --check --diff .
	ruff check --diff .
	mypy

# This target auto-fixes lint issues where possible
style:
	ruff format .
	ruff check --fix .
