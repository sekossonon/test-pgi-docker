#!/bin/bash

shopt -s globstar nulljob dotglob

for f in /odoo/custom_addons/16.0/*/requirements.txt; do
    pip install --no-cache-dir -r $f;
done
