# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.177.0/containers/python-3/.devcontainer/base.Dockerfile

# [Choice] Python version: 3, 3.12, 3.13, 3.14
ARG VARIANT="3.12"
FROM mcr.microsoft.com/devcontainers/python:1-${VARIANT}

# [Optional] Uncomment this section to install additional OS packages.
# RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
#     && apt-get -y install --no-install-recommends <your-package-list-here>

RUN pip3 install uv

# Set the default shell to bash instead of sh
ENV SHELL /bin/bash
