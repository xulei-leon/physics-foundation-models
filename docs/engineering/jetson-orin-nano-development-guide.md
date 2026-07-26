# Jetson Orin Nano Super Docker Development Guide

## Purpose and isolation model

This guide uses Docker on an NVIDIA Jetson Orin Nano Super Developer Kit with
8 GB memory. It keeps particleML development dependencies out of the native
JetPack installation.

The host provides only:

- the NVIDIA-supported JetPack 6.x operating system;
- the Docker Engine already supplied or installed through the supported
  JetPack procedure;
- an existing user-owned repository directory;
- an existing user-owned NVMe runtime directory.

The container provides:

- ARM64 Ubuntu 22.04;
- Python 3.10 and the locked Python development dependencies;
- Node.js 20.19.5 and pnpm 10.33.0;
- compilers and native libraries required by ARM64 scientific packages;
- fixed numerical thread limits suitable for an 8 GB board.

The container does not require CUDA, PyTorch, TensorFlow, GPU-enabled XGBoost,
the NVIDIA container runtime, `--privileged`, host networking, or the Docker
socket. The project uses CPU implementations of scikit-learn, XGBoost, MLP,
and pyhf.

The repository and runtime directories are bind-mounted. Source changes,
download caches, and immutable artifacts therefore survive container
recreation. Python, Node.js, pnpm, compilers, and installed packages remain
inside the image or container writable layer.

## 1. Verify the unmodified Jetson host

Do not install Python, Node.js, pnpm, project compilers, swap files, or
particleML packages on the host.

Confirm the architecture, JetPack release, Docker availability, memory, and
existing NVMe storage:

```bash
uname -m
cat /etc/os-release
head -n 1 /etc/nv_tegra_release
docker version
docker info --format '{{.Architecture}}'
free -h
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
df -h
```

Expected architecture output is `aarch64`. Docker must report an ARM64
architecture. If Docker is missing or unhealthy, stop and repair it through
the NVIDIA-supported JetPack process. Do not use a remote convenience script
to replace the JetPack Docker stack.

If the current user cannot access Docker, use the site's approved Docker
access procedure. Adding a user to the `docker` group grants root-equivalent
host privileges and must not be done casually.

No setup step in this guide changes `/etc/fstab`, host swap, `nvpmodel`,
`jetson_clocks`, host Python, or host Node.js.

## 2. Place source and runtime data on existing NVMe storage

Choose an already mounted, user-writable NVMe directory. The examples use
`/mnt/nvme/particleml`; replace it if the board uses a different mount.

```bash
export PARTICLEML_HOST_ROOT=/mnt/nvme/particleml
mkdir -p "$PARTICLEML_HOST_ROOT"
cd "$PARTICLEML_HOST_ROOT"

git clone https://github.com/xulei-leon/particleML.git particleML
mkdir -p runtime/{artifacts,cache,tmp}
```

For an existing checkout, skip `git clone` and set
`PARTICLEML_HOST_ROOT` to the directory containing that checkout and the
`runtime` directory.

Confirm that every bind-mount source is user-owned and is located on the
intended filesystem:

```bash
stat -c '%U:%G %n' \
  "$PARTICLEML_HOST_ROOT/particleML" \
  "$PARTICLEML_HOST_ROOT/runtime"
df -h "$PARTICLEML_HOST_ROOT"
```

Do not copy `.venv` or `node_modules` from an x86-64 machine. They are excluded
from the Docker build context and must be created for ARM64.

## 3. Review the container boundary

Enter the repository and inspect the Dockerfile before building:

```bash
cd "$PARTICLEML_HOST_ROOT/particleML"
sed -n '1,240p' docker/jetson-dev/Dockerfile
```

The Dockerfile is intentionally ARM64-only and fails its build when the base
image architecture is not `arm64`. Its Node.js archive is downloaded over
direct HTTPS and verified against the upstream `SHASUMS256.txt`.

The runtime command later in this guide mounts only:

```text
HOST particleML repository  -> /workspace/particleML
HOST runtime directory      -> /workspace/runtime
```

Do not add mounts for `/`, `/etc`, `/usr`, `/var/lib/docker`, `/dev`, or
`/var/run/docker.sock`. Do not add `--privileged`.

## 4. Build the ARM64 development image

Build with the host user's numeric UID and GID. Matching IDs prevent the
container from creating root-owned files in the bind mounts:

```bash
cd "$PARTICLEML_HOST_ROOT/particleML"

export PARTICLEML_HOST_UID="$(id -u)"
export PARTICLEML_HOST_GID="$(id -g)"
export PARTICLEML_DEV_IMAGE=particleml-jetson-dev:0.3.0

test "$PARTICLEML_HOST_UID" -gt 0
test "$PARTICLEML_HOST_GID" -gt 0

docker build \
  --pull \
  --build-arg HOST_UID="$PARTICLEML_HOST_UID" \
  --build-arg HOST_GID="$PARTICLEML_HOST_GID" \
  --file docker/jetson-dev/Dockerfile \
  --tag "$PARTICLEML_DEV_IMAGE" \
  .
```

This is the only step that installs operating-system and language packages,
and it installs them inside image layers. A failed ARM64 wheel installation
stops the build without changing JetPack.

Inspect the resulting image:

```bash
docker image inspect "$PARTICLEML_DEV_IMAGE" \
  --format '{{.Architecture}} {{.Os}} {{.Size}}'

docker run --rm "$PARTICLEML_DEV_IMAGE" \
  bash -lc 'uname -m; python --version; node --version; pnpm --version'
```

Expected values include `arm64`/`aarch64`, Python 3.10, Node.js 20.19.5, and
pnpm 10.33.0.

## 5. Create the persistent development container

The 8 GB board must retain memory for JetPack and the Docker daemon. The
container is limited to 7 GiB, six CPUs, four native numerical threads, and a
1 GiB shared-memory area:

```bash
export PARTICLEML_DEV_CONTAINER=particleml-dev

docker run \
  --detach \
  --init \
  --name "$PARTICLEML_DEV_CONTAINER" \
  --cpus 6 \
  --memory 7g \
  --shm-size 1g \
  --mount \
    "type=bind,src=$PARTICLEML_HOST_ROOT/particleML,dst=/workspace/particleML" \
  --mount \
    "type=bind,src=$PARTICLEML_HOST_ROOT/runtime,dst=/workspace/runtime" \
  --env OMP_NUM_THREADS=4 \
  --env OPENBLAS_NUM_THREADS=4 \
  --env MKL_NUM_THREADS=4 \
  --env NUMEXPR_NUM_THREADS=4 \
  --env TMPDIR=/workspace/runtime/tmp \
  "$PARTICLEML_DEV_IMAGE"
```

This command uses Docker's default bridge network, which is sufficient for
direct HTTPS package and catalog access. It does not expose ports, devices, or
host system directories.

Confirm the mounts, limits, and non-root user:

```bash
docker inspect "$PARTICLEML_DEV_CONTAINER" \
  --format '{{json .Mounts}}'
docker inspect "$PARTICLEML_DEV_CONTAINER" \
  --format 'memory={{.HostConfig.Memory}} cpus={{.HostConfig.NanoCpus}}'
docker exec "$PARTICLEML_DEV_CONTAINER" id
```

## 6. Initialize the mounted checkout inside the container

Open a shell:

```bash
docker exec --interactive --tty "$PARTICLEML_DEV_CONTAINER" bash
```

Run the following commands inside that shell:

```bash
cd /workspace/particleML

python -m pip install --no-deps --editable .
pnpm install --frozen-lockfile

python -c "import platform, sys; print(platform.machine(), sys.version)"
python -c "import numpy, pyarrow, sklearn, xgboost; print(numpy.__version__, pyarrow.__version__, sklearn.__version__, xgboost.__version__)"
node -p "process.arch"
particleml --help
```

Expected Python architecture is `aarch64`, and Node.js must report `arm64`.
The editable Python installation points to the bind-mounted source tree.

`node_modules` is also created inside the mounted checkout with the matching
host UID/GID. It is ignored by Git and must not be copied to another
architecture.

## 7. Verify the container environment

Run all checks inside the container:

```bash
cd /workspace/particleML

particleml contracts validate
python -m pytest -q tests/test_config.py tests/test_contracts.py
python -m pytest -q
python -m ruff check src/particleml scripts tests
python -m mypy src/particleml
python scripts/validate_software_docs.py
pnpm test
pnpm docs:build
```

The default Python tests use generated ROOT and Parquet fixtures and must not
access the network. Passing them verifies the containerized software
environment. It does not validate a physics result or authorize unblinding.

## 8. Daily development workflow

Start an existing stopped container from the Jetson host:

```bash
export PARTICLEML_DEV_CONTAINER=particleml-dev
docker start "$PARTICLEML_DEV_CONTAINER"
docker exec --interactive --tty "$PARTICLEML_DEV_CONTAINER" bash
```

Inside the container:

```bash
cd /workspace/particleML
git status --short

python -m pytest -q tests/test_ingestion.py
python -m ruff check src/particleml scripts tests
python -m mypy src/particleml
python -m pytest -q
```

Edit files through the host checkout, an SSH editor, or an editor attached to
the running container. Select `/opt/particleml-venv/bin/python` as the
container Python interpreter.

Stop the container when development is finished:

```bash
docker stop "$PARTICLEML_DEV_CONTAINER"
```

Stopping or removing the container does not remove the bind-mounted source,
cache, or artifacts.

## 9. Interactive debugging

Run a command directly without opening a persistent shell:

```bash
docker exec --interactive --tty particleml-dev \
  python -m pytest -vv -s tests/test_ingestion.py -k normalization
```

Use Python's debugger inside the container:

```bash
docker exec --interactive --tty particleml-dev \
  bash -lc 'python -m pdb "$(command -v particleml)" contracts validate'
```

For an editor with container support, attach to the existing
`particleml-dev` container. Do not mount the Docker socket into the container
to make this work.

## 10. Monitor memory without changing JetPack

Run `tegrastats` on the Jetson host in a separate terminal:

```bash
tegrastats
```

Inspect container use from another host terminal:

```bash
docker stats particleml-dev
```

Inspect memory and storage from inside the container:

```bash
free -h
df -h /workspace/particleML /workspace/runtime
```

If a process is killed for memory pressure:

1. confirm the container still has the documented 7 GiB limit;
2. reduce ROOT `--chunk-size` to 5,000 or 10,000;
3. run one focused test or model while debugging;
4. stop the VitePress development server;
5. retain all scientific seeds, sample roles, thresholds, and fit settings.

Do not solve a container OOM by modifying host swap, JetPack power modes, or
scientific configuration.

## 11. Use NVMe runtime paths for analysis commands

Inside the container, use `/workspace/runtime` for large mutable and immutable
outputs:

```bash
particleml catalog freeze \
  --config configs/catalog-sources.yaml \
  --cache /workspace/runtime/cache/atlas \
  --output /workspace/runtime/artifacts/catalog.json

particleml dataset build \
  --config configs/analysis-v1.yaml \
  --catalog /workspace/runtime/artifacts/catalog.json \
  --cache /workspace/runtime/cache/atlas \
  --output /workspace/runtime/artifacts/dataset-debug \
  --chunk-size 10000
```

Continue with the exact commands in the
[analysis run guide](analysis-run-guide.md), substituting
`/workspace/runtime/artifacts` for the artifact root.

Immutable outputs cannot be overwritten. Use a new debug path after a failed
or changed run. Do not change the allowlist, model features, split algorithm,
weights, formal seeds, DDT gates, template scaling, or fit contract to reduce
resource use.

Do not run `particleml analysis authorize` or `particleml analysis observed`
during ordinary development. Real events in the 120--130 GeV window remain
unread until a valid freeze and independent human authorization exist.

## 12. Rebuild after dependency changes

Changes to application source are visible immediately through the bind mount
and do not require an image rebuild.

Rebuild only when the Dockerfile, Python lock, Python package metadata, Node.js
version, or pnpm version changes:

```bash
docker stop particleml-dev
docker rm particleml-dev

cd "$PARTICLEML_HOST_ROOT/particleML"
docker build \
  --pull \
  --build-arg HOST_UID="$(id -u)" \
  --build-arg HOST_GID="$(id -g)" \
  --file docker/jetson-dev/Dockerfile \
  --tag particleml-jetson-dev:0.3.0 \
  .
```

Then repeat the container creation and checkout initialization steps. The
source and `/workspace/runtime` data remain intact because they are host bind
mounts.

Do not use `docker system prune`, delete the runtime directory, or remove
images and containers unrelated to particleML.

## 13. Completion checklist

The isolated Jetson development environment is ready when:

- the host remains on its supported JetPack image;
- host Python, Node.js, swap, power modes, and system packages were not changed
  for particleML;
- Docker and the development image report ARM64;
- the container runs as the matching non-root host UID/GID;
- only the repository and dedicated runtime directory are bind-mounted;
- Python 3.10, Node.js 20.19.5, and pnpm 10.33.0 are reported inside the
  container;
- all Python tests, Ruff, strict mypy, schema validation, documentation tests,
  and VitePress build pass inside the container;
- no real signal-window data, authorization artifact, or observed result was
  created during setup.
