FROM python:3.10-bookworm

COPY ./install /tmp/install

RUN chmod +x /tmp/install/*.sh /tmp/install/docker.sh && rm -r /tmp/install

ENTRYPOINT ["service", "docker", "start"]