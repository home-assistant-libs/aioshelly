#!/bin/bash

# Use copy mode for UV to avoid hardlink warnings on different filesystems
export UV_LINK_MODE=copy

# Always use this repo's .venv, even if the shell exports another project's
# environment (e.g. a shared devcontainer)
REPO_ROOT=$(cd -- "$(dirname -- "$0")/.." &>/dev/null && pwd)
export UV_PROJECT_ENVIRONMENT="$REPO_ROOT/.venv"
export VIRTUAL_ENV="$UV_PROJECT_ENVIRONMENT"

uv sync --all-groups
uv run prek install
