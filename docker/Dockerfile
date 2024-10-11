FROM python:3.10-alpine

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache libpq-dev gcc libc-dev

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --no-cache-dir luigi==3.3.0 psycopg2==2.9.5 sqlalchemy==1.3.24

RUN mkdir -p /var/lib/luigi/data
RUN touch /var/lib/luigi/data/luigi.db
RUN mkdir /etc/luigi
ADD client.cfg /etc/luigi/client.cfg

VOLUME /etc/luigi
VOLUME /var/lib/luigi

EXPOSE 8082
CMD ["luigid"]
