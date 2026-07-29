ARG JETSON_PYTORCH_IMAGE=nvcr.io/nvidia/pytorch:25.06-py3-igpu
FROM ${JETSON_PYTORCH_IMAGE}

USER root

ARG DEBIAN_FRONTEND=noninteractive
ARG HOST_UID=1000
ARG HOST_GID=1000
ARG NODE_VERSION=v20.19.5
ARG XGBOOST_VERSION=3.3.0
ARG XGBOOST_CUDA_ARCHITECTURES=87
ARG XGBOOST_SOURCE_SHA256=58bcb8a4cace648cdab7b94fa4f16d2c9ff26d90dd4d26907168106fa06d8746

ENV VIRTUAL_ENV=/opt/particleml-venv
ENV PATH=/opt/particleml-venv/bin:/opt/node/bin:${PATH}
ENV HOME=/home/particleml
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV OMP_NUM_THREADS=4
ENV OPENBLAS_NUM_THREADS=4
ENV MKL_NUM_THREADS=4
ENV NUMEXPR_NUM_THREADS=4
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

RUN test "$(dpkg --print-architecture)" = "arm64" \
    && apt-get update \
    && apt-get install --yes --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        curl \
        git \
        libgomp1 \
        ninja-build \
        pkg-config \
        procps \
        python3 \
        python3-dev \
        python3-venv \
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
    && python3 -m venv "${VIRTUAL_ENV}" \
    && python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install \
        --requirement /tmp/particleml-build/requirements-ci.lock \
    && command -v nvcc \
    && curl --fail --location --output /tmp/xgboost.tar.gz \
        "https://files.pythonhosted.org/packages/fd/41/846d4de2b8fc694073fd3ac5052caf68caa1ea11cb7fa32d7ad9c049b232/xgboost-${XGBOOST_VERSION}.tar.gz" \
    && echo "${XGBOOST_SOURCE_SHA256}  /tmp/xgboost.tar.gz" | sha256sum --check \
    && mkdir /tmp/xgboost \
    && tar --extract --gzip --strip-components=1 --file /tmp/xgboost.tar.gz --directory /tmp/xgboost \
    && cmake -S /tmp/xgboost/cpp_src -B /tmp/xgboost/build -GNinja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CUDA_ARCHITECTURES="${XGBOOST_CUDA_ARCHITECTURES}" \
        -DKEEP_BUILD_ARTIFACTS_IN_BINARY_DIR=ON \
        -DUSE_CUDA=ON \
    && cmake --build /tmp/xgboost/build --parallel 2 \
    && install --directory /tmp/lib \
    && install /tmp/xgboost/build/lib/libxgboost.so /tmp/lib/libxgboost.so \
    && test -e /tmp/lib/libxgboost.so \
    && python -m pip install --no-deps --force-reinstall --no-build-isolation \
        /tmp/xgboost \
    && mkdir -p "${HOME}" /workspace/particleML /workspace/runtime/tmp \
    && chown -R "${HOST_UID}:${HOST_GID}" \
        "${VIRTUAL_ENV}" \
        /workspace \
        "${HOME}" \
    && rm -rf /tmp/lib /tmp/particleml-build /tmp/xgboost /tmp/xgboost.tar.gz

ENV TMPDIR=/workspace/runtime/tmp

USER ${HOST_UID}:${HOST_GID}
WORKDIR /workspace/particleML

CMD ["sleep", "infinity"]
