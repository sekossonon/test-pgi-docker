#!/bin/bash

container_name='odoo'
if [ ! -z "$WORKSPACE" ]; then
    container_name=$WORKSPACE'_'$container_name
fi
echo $JOB_NAME
echo $NODE_NAME
docker exec -it $container_name -1 -u odoo sh -c "odoo-bin -d test_db -i microcom_ts --test-enable --stop-after-init"
