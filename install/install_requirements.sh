#!/bin/bash


shopt -s globstar
for f in /odoo/custom_modules/16.0/*/requirement.txt; do
    pip install -r $f;
done
