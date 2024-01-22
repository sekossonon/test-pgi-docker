#!/bin/bash

shopt -s globstar nulljob dotglob

for f in /odoo/custom_modules/16.0/*/requirement.txt; do
    pip install -r $f;
done
