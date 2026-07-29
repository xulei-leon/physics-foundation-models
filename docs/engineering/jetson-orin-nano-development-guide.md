# Jetson Orin Nano Super Docker Development Guide

## Purpose and isolation model

This guide uses Docker on an NVIDIA Jetson Orin Nano Super Developer Kit with
8 GB memory. The host stores the checkout and supports basic operating-system
tools; Docker supplies the particleML-specific dependencies and debugging
environment.

The host provides only:

- the NVIDIA-supported JetPack 6.x operating system;
- the Docker Engine already supplied or installed through the supported
  JetPack procedure;
- Docker Buildx;
- basic host tools required to prepare the checkout, including Git and CA
  certificates;
- a user-owned checkout and runtime directory on NVMe storage.

The container is built from `nvcr.io/nvidia/pytorch:25.06-py3-igpu` and
provides:

- the ARM64 CUDA 12.9 and PyTorch runtime supplied by the base image;
- Python 3.12 and the locked particleML development dependencies;
- XGBoost 3.3.0 compiled from source for the Orin SM 8.7 GPU;
- Node.js 20.19.5 and pnpm 10.33.0;
- compilers and native libraries required by ARM64 scientific packages;
- fixed numerical thread limits suitable for an 8 GB board.

The container uses the NVIDIA Container Toolkit and CUDA for GPU-enabled
XGBoost development and formal training. The base image includes PyTorch, but
particleML does not depend on it. The workflow does not require TensorFlow,
`--privileged`, or the Docker socket. It uses host networking only for this
board's documented Docker bridge workaround. The formal particleML
configuration uses the validated CUDA backend with `tree_method: hist` and
`device: cuda`.

The repository and runtime directories are bind-mounted. Source changes,
download caches, and immutable artifacts therefore survive container
recreation. ParticleML-specific Python and Node.js packages, compilers, and
debugging tools remain inside the image or container writable layer.

## 1. Verify the Jetson host baseline

The host may store the checkout on NVMe and install basic system packages
needed to work with it. Keep particleML-specific Python and Node.js packages,
project compilers, and debugging dependencies in Docker.

Confirm the architecture, JetPack release, Docker availability, memory, and
existing NVMe storage:

```bash
$ uname -m
aarch64

$ cat /etc/os-release
PRETTY_NAME="Ubuntu 22.04.5 LTS"
NAME="Ubuntu"
VERSION_ID="22.04"
VERSION="22.04.5 LTS (Jammy Jellyfish)"
VERSION_CODENAME=jammy
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=jammy

$ head -n 1 /etc/nv_tegra_release
# R36 (release), REVISION: 4.3, GCID: 38968081, BOARD: generic, EABI: aarch64, DATE: Wed Jan  8 01:49:37 UTC 2025

$ sudo docker version
Client:
 Version:           29.1.3
 API version:       1.52
 Go version:        go1.24.4
 Git commit:        29.1.3-0ubuntu3~22.04.2
 Built:             Wed Apr 29 22:18:59 2026
 OS/Arch:           linux/arm64
 Context:           default

Server:
 Engine:
  Version:          29.1.3
  API version:      1.52 (minimum version 1.44)
  Go version:       go1.24.4
  Git commit:       29.1.3-0ubuntu3~22.04.2
  Built:            Wed Apr 29 22:18:59 2026
  OS/Arch:          linux/arm64
  Experimental:     false
 containerd:
  Version:          2.2.1
  GitCommit:
 runc:
  Version:          1.3.4-0ubuntu1~22.04.1
  GitCommit:
 docker-init:
  Version:          0.19.0
  GitCommit:

$ sudo docker info --format '{{.Architecture}}'
aarch64

$ free -h
               total        used        free      shared  buff/cache   available
Mem:           7.4Gi       1.4Gi       4.6Gi        29Mi       1.4Gi       5.8Gi
Swap:          3.7Gi

$ lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
NAME           SIZE FSTYPE   MOUNTPOINTS
loop0            4K          /snap/bare/5
loop1        191.1M          /snap/chromium/3488
loop2           69M          /snap/core22/2412
loop3         61.9M          /snap/core24/1644
loop4         47.9M          /snap/cups/1231
loop5        552.9M          /snap/gnome-46-2404/154
loop6         91.7M          /snap/gtk-common-themes/1535
loop7        188.2M          /snap/mesa-2404/1836
loop8         43.4M squashfs /snap/snapd/27407
loop9         43.4M squashfs /snap/snapd/27595
loop10          16M
zram0          635M          [SWAP]
zram1          635M          [SWAP]
zram2          635M          [SWAP]
zram3          635M          [SWAP]
zram4          635M          [SWAP]
zram5          635M          [SWAP]
nvme0n1      238.5G
├─nvme0n1p1    237G ext4     /
├─nvme0n1p2    128M
├─nvme0n1p3    768K
├─nvme0n1p4   31.6M
├─nvme0n1p5    128M
├─nvme0n1p6    768K
├─nvme0n1p7   31.6M
├─nvme0n1p8     80M
├─nvme0n1p9    512K
├─nvme0n1p10    64M vfat     /boot/efi
├─nvme0n1p11    80M
├─nvme0n1p12   512K
├─nvme0n1p13    64M
├─nvme0n1p14   400M
└─nvme0n1p15 479.5M

$ df -h
Filesystem       Size  Used Avail Use% Mounted on
/dev/nvme0n1p1   233G   35G  189G  16% /
tmpfs            3.8G  120K  3.8G   1% /dev/shm
tmpfs            1.5G   27M  1.5G   2% /run
tmpfs            5.0M  4.0K  5.0M   1% /run/lock
/dev/nvme0n1p10   63M  110K   63M   1% /boot/efi
tmpfs            763M  108K  762M   1% /run/user/1000
```

Expected architecture output is `aarch64`. Docker must report an ARM64
architecture. If Docker is missing or unhealthy, stop and repair it through
the NVIDIA-supported JetPack process. Do not use a remote convenience script
to replace the JetPack Docker stack.

Confirm that the cached CUDA base image is ARM64 and that Docker can expose the
Jetson GPU before building the development image:

```bash
export JETSON_PYTORCH_IMAGE=nvcr.io/nvidia/pytorch:25.06-py3-igpu

sudo docker image inspect "$JETSON_PYTORCH_IMAGE" \
  --format '{{.Architecture}} {{.Id}}'
sudo docker run --rm --network none --runtime nvidia --entrypoint sh "$JETSON_PYTORCH_IMAGE" \
  -c 'test -e /dev/nvhost-gpu || test -e /dev/nvidia0'
```

This command must exit successfully. This Jetson runtime requires
`--runtime nvidia`; do not substitute `--gpus all`. If it fails, repair the
NVIDIA Container Toolkit installation through the supported JetPack procedure;
do not replace the JetPack CUDA stack from inside the container.

Run the Docker commands in this guide with `sudo`. Do not add a user to the
`docker` group solely for this workflow because that group grants root-equivalent
host privileges.

No setup step in this guide changes `/etc/fstab`, host swap, `nvpmodel`,
`jetson_clocks`, host Python, or host Node.js.

Install the host tools needed for a verified HTTPS checkout and BuildKit image
builds:

```bash
sudo apt update
sudo apt install --yes git ca-certificates docker-buildx
sudo docker buildx version
sudo docker info --format '{{json .Runtimes}}' | grep -q '"nvidia"'
```

## 2. Place source and runtime data on existing NVMe storage

The verified board stores its root filesystem on `nvme0n1p1`, so `~/code` is
already on NVMe. Keep both the checkout and its runtime data there.

```bash
export PARTICLEML_HOST_ROOT="$HOME/code/particleML"

git clone https://github.com/xulei-leon/particleML.git "$PARTICLEML_HOST_ROOT"
mkdir -p "$PARTICLEML_HOST_ROOT/runtime"/{artifacts,cache,tmp}
```

For an existing checkout, skip `git clone` and set `PARTICLEML_HOST_ROOT` to
that checkout directory.

Confirm that every bind-mount source is user-owned and is located on the
intended filesystem:

```bash
$ stat -c '%U:%G %n' \
  "$PARTICLEML_HOST_ROOT" \
  "$PARTICLEML_HOST_ROOT/runtime"
leon:leon /home/leon/code/particleML
leon:leon /home/leon/code/particleML/runtime

$ df -h "$PARTICLEML_HOST_ROOT"
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p1  233G   35G  189G  16% /
```

Do not copy `.venv` or `node_modules` from an x86-64 machine. They are excluded
from the Docker build context and must be created for ARM64.

## 3. Review the container boundary

Enter the repository and inspect the Dockerfile before building:

```bash
cd "$PARTICLEML_HOST_ROOT"
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
container from creating root-owned files in the bind mounts. The image uses the
numeric IDs directly, so it remains compatible with base images that already
define the same UID or GID:

```bash
cd "$PARTICLEML_HOST_ROOT"

export PARTICLEML_HOST_UID="$(id -u)"
export PARTICLEML_HOST_GID="$(id -g)"
export PARTICLEML_DEV_IMAGE=particleml-jetson-dev:0.3.0
export JETSON_PYTORCH_IMAGE=nvcr.io/nvidia/pytorch:25.06-py3-igpu

test "$PARTICLEML_HOST_UID" -gt 0
test "$PARTICLEML_HOST_GID" -gt 0

sudo docker buildx build \
  --load \
  --network host \
  --build-arg JETSON_PYTORCH_IMAGE="$JETSON_PYTORCH_IMAGE" \
  --build-arg HOST_UID="$PARTICLEML_HOST_UID" \
  --build-arg HOST_GID="$PARTICLEML_HOST_GID" \
  --file docker/jetson-dev/Dockerfile \
  --tag "$PARTICLEML_DEV_IMAGE" \
  .
```

Buildx uses the locally cached CUDA base image and loads the resulting image
into the Docker daemon for `docker run`. This step installs particleML-specific
operating-system and language packages inside image layers. It downloads the
locked XGBoost 3.3.0 source distribution from PyPI, verifies its SHA-256, and
rebuilds it with `SM 87` CUDA support. Compilation is limited to two jobs for
the 8 GB board. This avoids a GitHub clone during the image build. A missing
`nvcc`, failed download verification, or failed ARM64 build stops the build
without changing JetPack.

Inspect the resulting image:

```bash
$ sudo docker image ls
IMAGE                                   ID             DISK USAGE   CONTENT SIZE   EXTRA
nvcr.io/nvidia/pytorch:25.06-py3-igpu   05bb8855c5ab       17.4GB         5.11GB
particleml-jetson-dev:0.3.0             2c8af9f52080       21.5GB         6.57GB
leon@leon-orin:~/code/particleML$

$ sudo docker image inspect "$PARTICLEML_DEV_IMAGE" \
  --format '{{.Architecture}} {{.Os}} {{.Size}}'
arm64 linux 6565709207

$ sudo docker run --rm --network none --runtime nvidia "$PARTICLEML_DEV_IMAGE" \
  bash -lc 'uname -m; python --version; node --version; pnpm --version'
aarch64
Python 3.12.3
v20.19.5
10.33.0

```

Expected values include `arm64`/`aarch64`, Python 3.12, Node.js 20.19.5, and
pnpm 10.33.0.

## 5. Create the persistent development container

The 8 GB board must retain memory for JetPack and the Docker daemon. The
container is limited to 7 GiB, six CPUs, four native numerical threads, and a
1 GiB shared-memory area:

```bash
export PARTICLEML_DEV_CONTAINER=particleml-dev

sudo docker container stop "$PARTICLEML_DEV_CONTAINER"

sudo docker container rm "$PARTICLEML_DEV_CONTAINER"

sudo docker run \
  --detach \
  --init \
  --name "$PARTICLEML_DEV_CONTAINER" \
  --network host \
  --runtime nvidia \
  --cpus 6 \
  --memory 7g \
  --shm-size 1g \
  --mount \
    "type=bind,src=$PARTICLEML_HOST_ROOT,dst=/workspace/particleML" \
  --mount \
    "type=bind,src=$PARTICLEML_HOST_ROOT/runtime,dst=/workspace/runtime" \
  --env OMP_NUM_THREADS=4 \
  --env OPENBLAS_NUM_THREADS=4 \
  --env MKL_NUM_THREADS=4 \
  --env NUMEXPR_NUM_THREADS=4 \
  --env TMPDIR=/workspace/runtime/tmp \
  "$PARTICLEML_DEV_IMAGE"
```

This board's Docker bridge cannot create its legacy iptables `raw` rule, so the
container uses the host network for direct HTTPS package and catalog access.
It does not publish ports or mount host system directories beyond the GPU
devices and driver libraries injected by the NVIDIA Container Toolkit.

Confirm the mounts, limits, and non-root user:

```bash
$ sudo docker container ls
CONTAINER ID   IMAGE                         COMMAND                  CREATED          STATUS          PORTS     NAMES
06d9f909e262   particleml-jetson-dev:0.3.0   "/opt/nvidia/nvidia_…"   14 minutes ago   Up 14 minutes             particleml-dev

$ sudo docker inspect "$PARTICLEML_DEV_CONTAINER" \
  --format '{{json .Mounts}}'
[{"Type":"bind","Source":"/home/leon/code/particleML","Destination":"/workspace/particleML","Mode":"","RW":true,"Propagation":"rprivate"},{"Type":"bind","Source":"/home/leon/code/particleML/runtime","Destination":"/workspace/runtime","Mode":"","RW":true,"Propagation":"rprivate"}]

$ sudo docker inspect "$PARTICLEML_DEV_CONTAINER" \
  --format 'memory={{.HostConfig.Memory}} cpus={{.HostConfig.NanoCpus}}'
memory=7516192768 cpus=6000000000

$ sudo docker exec "$PARTICLEML_DEV_CONTAINER" id
uid=1000(ubuntu) gid=1000(ubuntu) groups=1000(ubuntu)
```

## 6. Initialize the mounted checkout inside the container

Open a shell:

```bash
sudo docker exec --interactive --tty "$PARTICLEML_DEV_CONTAINER" bash
```

Run the following commands inside that shell:

```bash
cd /workspace/particleML

python -m pip install --no-deps --editable .
pnpm install --frozen-lockfile
```

Check the Python and Node.js versions, architecture, and installed packages:

```bash
$ python -c "import platform, sys; print(platform.machine(), sys.version)"
aarch64 3.12.3 (main, Feb  4 2025, 14:48:35) [GCC 13.3.0]

$ python -c "import numpy, pyarrow, sklearn, xgboost; print(numpy.__version__, pyarrow.__version__, sklearn.__version__, xgboost.__version__)"
1.26.4 21.0.0 1.7.2 3.3.0

$ node -p "process.arch"
arm64

$ particleml --help
usage: particleml [-h] {catalog,dataset,audit,run,study,decorrelate,evaluate,analysis,fit,report,contracts} ...

positional arguments:
  {catalog,dataset,audit,run,study,decorrelate,evaluate,analysis,fit,report,contracts}

options:
  -h, --help            show this help message and exit
```

Expected Python architecture is `aarch64`, and Node.js must report `arm64`.
The editable Python installation points to the bind-mounted source tree.

`node_modules` is also created inside the mounted checkout with the matching
host UID/GID. It is ignored by Git and must not be copied to another
architecture.

Confirm that XGBoost uses CUDA rather than silently falling back to CPU:

```bash
$ python - <<'PY'
import json

import numpy as np
from xgboost import XGBClassifier

model = XGBClassifier(tree_method="hist", device="cuda", n_estimators=1)
model.fit(np.array([[0.0], [1.0]]), np.array([0, 1]))
device = json.loads(model.get_booster().save_config())["learner"]["generic_param"]["device"]
assert device in {"cuda", "cuda:0"}, device
print("XGBoost CUDA device:", device)
PY

XGBoost CUDA device: cuda:0
```

This check matches the committed formal XGBoost device and tree method.
Changing either setting requires a new reviewed configuration and new
artifacts.

## 7. Verify the container environment

Run all checks inside the container:

```bash
cd /workspace/particleML

export PARTICLEML_PYTEST_CACHE=/workspace/runtime/tmp/pytest-cache
export RUFF_CACHE_DIR=/workspace/runtime/tmp/ruff-cache
export PARTICLEML_MYPY_CACHE=/workspace/runtime/tmp/mypy-cache

$ particleml contracts validate
dataset-catalog
dataset-manifest
split-manifest
run-record
prediction-metadata
model-metadata
tuning-decision
study-result
analysis-freeze
unblinding-authorization
fit-result

$ python -m pytest -q -o cache_dir="$PARTICLEML_PYTEST_CACHE" tests/test_config.py tests/test_contracts.py
17 passed in 0.48s

$ python -m pytest -q -o cache_dir="$PARTICLEML_PYTEST_CACHE"
76 passed, 15 warnings in 20.31s

$ python -m ruff check src/particleml scripts tests
All checks passed!

$ python -m mypy --cache-dir="$PARTICLEML_MYPY_CACHE" src/particleml
Success: no issues found in 22 source files

$ python scripts/validate_software_docs.py
documentation validation passed (7 checks)

pnpm test
pnpm docs:build
```

The default Python tests use generated ROOT and Parquet fixtures and must not
access the network. Passing them verifies the containerized software
environment. It does not validate a physics result or authorize unblinding.
The tool caches are kept under `/workspace/runtime/tmp` so a pre-existing
root-owned cache in the bind-mounted checkout cannot block verification.

## 8. Daily development workflow

Start an existing stopped container from the Jetson host:

```bash
export PARTICLEML_DEV_CONTAINER=particleml-dev
sudo docker start "$PARTICLEML_DEV_CONTAINER"
sudo docker exec --interactive --tty "$PARTICLEML_DEV_CONTAINER" bash
```

Inside the container:

```bash
cd /workspace/particleML
git status --short

export PARTICLEML_PYTEST_CACHE=/workspace/runtime/tmp/pytest-cache
export RUFF_CACHE_DIR=/workspace/runtime/tmp/ruff-cache
export PARTICLEML_MYPY_CACHE=/workspace/runtime/tmp/mypy-cache

python -m pytest -q -o cache_dir="$PARTICLEML_PYTEST_CACHE" tests/test_ingestion.py
python -m ruff check src/particleml scripts tests
python -m mypy --cache-dir="$PARTICLEML_MYPY_CACHE" src/particleml
python -m pytest -q -o cache_dir="$PARTICLEML_PYTEST_CACHE"
```

Edit files through the host checkout, an SSH editor, or an editor attached to
the running container. Select `/opt/particleml-venv/bin/python` as the
container Python interpreter.

Stop the container when development is finished:

```bash
sudo docker stop "$PARTICLEML_DEV_CONTAINER"
```

Stopping or removing the container does not remove the bind-mounted source,
cache, or artifacts.

## 9. Interactive debugging

Run a command directly without opening a persistent shell:

```bash
sudo docker exec --interactive --tty particleml-dev \
  python -m pytest -vv -s tests/test_ingestion.py -k normalization
```

Use Python's debugger inside the container:

```bash
sudo docker exec --interactive --tty particleml-dev \
  bash -lc 'python -m pdb "$(command -v particleml)" contracts validate'
```

For an editor with container support, attach to the existing
`particleml-dev` container. Do not mount the Docker socket into the container
to make this work.

## 10. Monitor memory without changing JetPack

Run `tegrastats` on the Jetson host in a separate terminal:

```bash
$ tegrastats
07-29-2026 18:00:27 RAM 2272/7620MB (lfb 4x4MB) SWAP 221/3810MB (cached 0MB) CPU [0%@729,0%@1036,0%@1036,0%@1036,0%@729,0%@729] GR3D_FREQ 0% cpu@54.937C soc2@55.562C soc0@56.156C gpu@55.468C tj@56.656C soc1@56.656C VDD_IN 4673mW/4673mW VDD_CPU_GPU_CV 527mW/527mW VDD_SOC 1339mW/1339mW
07-29-2026 18:00:28 RAM 2272/7620MB (lfb 4x4MB) SWAP 221/3810MB (cached 0MB) CPU [0%@729,0%@729,0%@729,0%@729,0%@729,0%@729] GR3D_FREQ 0% cpu@54.75C soc2@55.625C soc0@56C gpu@55.656C tj@56.593C soc1@56.593C VDD_IN 4673mW/4673mW VDD_CPU_GPU_CV 527mW/527mW VDD_SOC 1339mW/1339mW
```

Inspect container use from another host terminal:

```bash
$ sudo docker stats --no-stream "$PARTICLEML_DEV_CONTAINER"
CONTAINER ID   NAME             CPU %     MEM USAGE / LIMIT   MEM %     NET I/O   BLOCK I/O        PIDS
06d9f909e262   particleml-dev   0.00%     118.3MiB / 7GiB     1.65%     0B / 0B   158MB / 20.7MB   3
```

Inspect memory and storage from inside the container:

```bash
ubuntu@leon-orin:/workspace/particleML$ free -h
               total        used        free      shared  buff/cache   available
Mem:           7.4Gi       2.1Gi       533Mi        21Mi       5.1Gi       5.4Gi
Swap:          3.7Gi       221Mi       3.5Gi

ubuntu@leon-orin:/workspace/particleML$ df -h /workspace/particleML /workspace/runtime
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p1  233G   49G  174G  22% /workspace/particleML
/dev/nvme0n1p1  233G   49G  174G  22% /workspace/runtime

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
sudo docker stop particleml-dev
sudo docker rm particleml-dev

cd "$PARTICLEML_HOST_ROOT"
sudo docker buildx build \
  --load \
  --network host \
  --build-arg JETSON_PYTORCH_IMAGE=nvcr.io/nvidia/pytorch:25.06-py3-igpu \
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
- only basic host packages needed for Docker and HTTPS Git access were added;
- particleML-specific Python and Node.js packages, compilers, and debugging
  dependencies remain in Docker;
- Docker and the development image report ARM64;
- Docker exposes the Jetson GPU and the XGBoost CUDA check reports `cuda`;
- the container runs as the matching non-root host UID/GID;
- only the repository and dedicated runtime directory are bind-mounted;
- Python 3.12, Node.js 20.19.5, and pnpm 10.33.0 are reported inside the
  container;
- all Python tests, Ruff, strict mypy, schema validation, documentation tests,
  and VitePress build pass inside the container;
- no real signal-window data, authorization artifact, or observed result was
  created during setup.
