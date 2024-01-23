#!/bin/bash
docker exec -it odoo-1 -u odoo sh -c "odoo-bin -d test_db -i microcom_ts --test-enable --stop-after-init"