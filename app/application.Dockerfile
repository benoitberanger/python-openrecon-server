# import python-openrecon-server as starting point
FROM python-openrecon-server AS base

LABEL version="1.0.1"

COPY . .
