#!/bin/bash
echo 'cloning odoo-common 16'
git clone --branch=16.0 --depth=1 https://$GITHUB_CREDS_USR:$GITHUB_CREDS_PSW@github.com/microcom/odoo-common.git
mv ./odoo-common ./src/projects/
echo 'clone oca/project'
git clone --branch=16.0 --depth=1 https://github.com/OCA/project.git
mv ./project ./src/projects/
sh 'ls -l ./src/projects/.'