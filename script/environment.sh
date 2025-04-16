#!/bin/bash

pip3 --disable-pip-version-check --no-cache-dir install .[dev] .[lint]
pip3 install -e .
pre-commit install
