FROM python:3.10-bookworm

COPY --chown=+x ./install /tmp/install

RUN chmod +x /tmp/install/*.sh
RUN ls /tmp/install
RUN /tmp/install/docker.sh
RUN rm -r /tmp/install

ENTRYPOINT ["docker", "run", "hello-world"]