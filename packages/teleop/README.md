# `teleop` (npm)

Node-friendly launcher for the **same Python camera-side stack** as the main repo: FastAPI + RealSense + WebRTC + cloud Socket.IO client.

| Registry | Package | Install |
|----------|---------|---------|
| **PyPI** | **`teleopsh`** | `pip install teleopsh` (Python module import name remains **`teleop`**) |
| **npm** | **`teleop`** | `npm install -g teleop` or `npx teleop` |

The name **`teleop`** on PyPI was unavailable, so the Python distribution is **`teleopsh`**. The **npm** name stays **`teleop`**.

## Requirements

- **Python 3.10+** on the robot / camera host  
- Intel RealSense **drivers** and **`pyrealsense2`** for your platform  
- **`pip install teleopsh`** (or **`pip install -e .`** from a clone of the parent repo)

`npx teleop` does **not** embed Python; it runs **`python -m teleop`** using your PATH or **`TELEOP_PYTHON`**.

## Install (Python)

From the parent repository (development):

```bash
cd /path/to/realsense-restapi
pip install -e .
```

From PyPI:

```bash
pip install teleopsh
```

Verify:

```bash
python -m teleop --help
teleopsh --help
```

## Run (npm / npx)

After the Python package is available in the environment **`npx`/`node` uses** (same machine, or set **`TELEOP_PYTHON`** to your venv’s `python.exe`):

```bash
npx teleop -- --cloud http://localhost:3001 --robot-id my-robot-1
```

- A leading **`--`** after `npx teleop` is optional; the launcher **strips** it so Python’s argparse never sees a stray `--`.  
- If npm swallows flags, keep the **`--`** separator.  
- **`TELEOP_PYTHON`**: absolute path to `python` / `python3` / venv interpreter (Windows example: `C:\path\to\venv\Scripts\python.exe`).

## Run (pip / Python only)

```bash
teleopsh --cloud http://localhost:3001 --robot-id my-robot-1
# or
python -m teleop --cloud http://localhost:3001 --robot-id my-robot-1
```

### API port

The stack listens on **`--port`** (default **8000**). If you see “address already in use”, pick another port or stop the conflicting process:

```bash
npx teleop -- --cloud http://localhost:3001 --robot-id my-robot-1 --port 8001
```

## Related docs

- Root overview: [../README.md](../README.md)  
- Cloud robot flow: [../CLOUD_ARCHITECTURE.md](../CLOUD_ARCHITECTURE.md)

## Publishing to npmjs

Sources live under **`packages/teleop/`** in the repo (this file + **`bin/`** only).

### Maintainer setup

1. Account: **https://www.npmjs.com/signup** (enable **2FA** if required to publish).  
2. **`npm login`** then **`npm whoami`**.  
3. Set **`repository.url`** (and optionally **`homepage`**, **`bugs`**) in **`package.json`** to your real Git URL.

### Dry run

```bash
cd packages/teleop
npm pack
```

Inspect the `.tgz` for `package/bin/teleop.cjs` and `package/README.md`.

### Publish

```bash
cd packages/teleop
npm publish
```

Unscoped **`teleop`** is public by default; **`--access public`** is only needed for scoped packages like **`@org/teleop`**.

### Versions

Bump **`"version"`** in **`package.json`** for every new release; npm does not allow re-uploading the same version.
