#!/bin/bash

container_name='odoo'
if [ ! -z "$WORKSPACE" ]; then
    container_name=$WORKSPACE'_'$container_name
fi

docker exec -it odoo-1 -u odoo sh -c "odoo-bin -d test_db -i microcom_ts --test-enable --stop-after-init"