#!/bin/bash

container_name='odoo'
if [ ! -z "$WORKSPACE" ]; then
    # docker container name gets pre-pended with the jenkins workspace folder name
    # so we need to do the same to get the real container name
    container_name="$(echo $WORKSPACE | rev | cut -d'/' -f 1 | rev)-$container_name-1"
fi

#docker compose build odoo # only destroy and rebuild odoo container
docker compose up -d
docker exec -u odoo $container_name sh -c "odoo --workers 0 -d test_db -i microcom_ts --test-tags=/microcom_ts --stop-after-init" \
    2>&1 | tee test_result.txt

error_lines=(`grep -n -x " ERROR " test_result.txt`)
if [ ${#error_lines[*]} > 0 ]; then
    exit 1
fi

# docker ps
# docker ps -a -q -f name=jenkins-docker1