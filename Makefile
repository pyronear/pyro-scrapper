# this target runs checks on all files and potentially modifies some of them
style:
	isort .
	black .
	ruff format .
	ruff check --fix .

quality:
	isort .
	flake8
	mypy
	pydocstyle

build:
	docker build . -t pyronear/pyro-etl

run-etl:
	docker run pyronear/pyro-etl:latest  /bin/sh -c "python /app/dl_images.py && python /app/predict_load.py"
