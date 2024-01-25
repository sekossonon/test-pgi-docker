#!/bin/bash

container_name='odoo'
if [ ! -z "$WORKSPACE" ]; then
    # docker container name gets pre-pended with the jenkins workspace folder name
    # so we need to do the same to be able to run the container
    container_name="$(echo $WORKSPACE | rev | cut -d'/' -f 1 | rev)-$container_name-1"
fi
docker compose up -d
docker ps
sleep 5
docker ps
docker exec $container_name sh -c "odoo -d test_db -i microcom_ts --test-enable --stop-after-init"
# docker ps -a -q -f name=jenkins-docker1
