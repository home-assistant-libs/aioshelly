#!/bin/bash

# Use copy mode for UV to avoid hardlink warnings on different filesystems
export UV_LINK_MODE=copy

pip3 --disable-pip-version-check --no-cache-dir install uv
uv venv .venv --seed --clear
source .venv/bin/activate
uv pip install --no-cache-dir -e .[dev] .[lint]
prek install
