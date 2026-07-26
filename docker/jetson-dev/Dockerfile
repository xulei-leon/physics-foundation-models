# syntax=docker/dockerfile:1

FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG HOST_UID=1000
ARG HOST_GID=1000
ARG NODE_VERSION=v20.19.5

ENV VIRTUAL_ENV=/opt/particleml-venv
ENV PATH=/opt/particleml-venv/bin:/opt/node/bin:${PATH}
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV OMP_NUM_THREADS=4
ENV OPENBLAS_NUM_THREADS=4
ENV MKL_NUM_THREADS=4
ENV NUMEXPR_NUM_THREADS=4

RUN test "$(dpkg --print-architecture)" = "arm64" \
    && apt-get update \
    && apt-get install --yes --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        libgomp1 \
        pkg-config \
        procps \
        python3.10 \
        python3.10-dev \
        python3.10-venv \
        python3-pip \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    archive="node-${NODE_VERSION}-linux-arm64.tar.xz"; \
    curl --fail --location --output "/tmp/${archive}" \
        "https://nodejs.org/dist/${NODE_VERSION}/${archive}"; \
    curl --fail --location --output /tmp/SHASUMS256.txt \
        "https://nodejs.org/dist/${NODE_VERSION}/SHASUMS256.txt"; \
    cd /tmp; \
    grep " ${archive}$" SHASUMS256.txt | sha256sum --check; \
    mkdir -p /opt/node; \
    tar --extract --xz --strip-components=1 --file "${archive}" --directory /opt/node; \
    rm -f "/tmp/${archive}" /tmp/SHASUMS256.txt; \
    corepack enable; \
    corepack prepare pnpm@10.33.0 --activate

COPY requirements-ci.lock pyproject.toml README.md LICENSE /tmp/particleml-build/

RUN test "${HOST_UID}" -gt 0 \
    && test "${HOST_GID}" -gt 0 \
    && python3.10 -m venv "${VIRTUAL_ENV}" \
    && python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install \
        --requirement /tmp/particleml-build/requirements-ci.lock \
    && groupadd --gid "${HOST_GID}" particleml \
    && useradd \
        --create-home \
        --gid "${HOST_GID}" \
        --shell /bin/bash \
        --uid "${HOST_UID}" \
        particleml \
    && mkdir -p /workspace/particleML /workspace/runtime/tmp \
    && chown -R particleml:particleml \
        "${VIRTUAL_ENV}" \
        /workspace \
        /home/particleml \
    && rm -rf /tmp/particleml-build

ENV TMPDIR=/workspace/runtime/tmp

USER particleml
WORKDIR /workspace/particleML

CMD ["sleep", "infinity"]
