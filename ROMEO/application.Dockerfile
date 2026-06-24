# import python-openrecon-server as starting point
FROM python-openrecon-server AS base

ARG JULIA_VERSION=1.10.9

RUN apt-get update && apt-get install -y curl procps

RUN curl -fsSL https://julialang-s3.julialang.org/bin/linux/x64/1.10/julia-${JULIA_VERSION}-linux-x86_64.tar.gz -o /tmp/julia.tar.gz \
    && tar -xzf /tmp/julia.tar.gz -C /opt \
    && ln -s /opt/julia-${JULIA_VERSION}/bin/julia /usr/local/bin/julia \
    && rm /tmp/julia.tar.gz

ENV JULIA_DEPOT_PATH=/opt/.julia
RUN julia -e 'import Pkg; Pkg.add(["ROMEO","MriResearchTools","ArgParse"]); Pkg.precompile()'

COPY ROMEO/romeo.jl /opt/romeo/romeo.jl

COPY . .

# Label with version of the app will be set automaticaly by the build.py script

# Command line will be added automaticaly by the build.py script

# Docker image metadata label `com.siemens-healthineers.magneticresonance.OpenRecon.metadata:1.1.0`
# will also be set automaticaly by the build.py script with the base64-encoded JSON text load from
# the json file provided in the app directory
