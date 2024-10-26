FROM pyronear/pyro-engine:latest

# set work directory
WORKDIR /usr/src/app


COPY requirements.txt requirements.txt
RUN pip install --default-timeout=500 -r requirements.txt \
    && pip cache purge \
    && rm -rf /root/.cache/pip

# Copy only the necessary application files
COPY src/ /usr/src/app
