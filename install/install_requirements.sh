#!/bin/bash


shopt -s globstar
for i in **/*.txt; do # Whitespace-safe and recursive
    process "$i"
done
for f in /odoo/custom_modules/16.0/*/requirement.txt; do
    pip install -r $f;
done
