# this target runs checks on all files and potentially modifies some of them
style:
	isort .
	black .


build-luigi-scheduler:
	@docker build ./docker -t luigi

stop-luigi-scheduler:
	@docker stop luigi

start-luigi-scheduler:
	@docker run -p 8082:8082 --name luigi -d luigi
