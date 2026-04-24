# import python-openrecon-server as starting point
FROM python-openrecon-server AS base

LABEL invertcontrast_version="1.0.3"

COPY . .

# Command line will be added automaticaly by the build.py script

# Docker image metadata label `com.siemens-healthineers.magneticresonance.OpenRecon.metadata:1.1.0`
# will also be set automaticaly by the build.py script with the base64-encoded JSON text load from
# the json file provided in the app directory
