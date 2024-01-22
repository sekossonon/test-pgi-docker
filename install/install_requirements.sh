#!/bin/bash

for requirement_file in /odoo/custom_modules/16.0/*/requirement.txt; 
    do pip install -r $requirement_file; 
done
