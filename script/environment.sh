#!/bin/bash

# Use copy mode for UV to avoid hardlink warnings on different filesystems
export UV_LINK_MODE=copy

uv sync --all-groups
uv run prek install
