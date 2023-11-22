#!/bin/bash

pip3 --disable-pip-version-check --no-cache-dir install -r requirements_dev.txt
pip3 install -e .
pre-commit install
