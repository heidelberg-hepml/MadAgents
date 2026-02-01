# MadAgents

[![arXiv](https://img.shields.io/badge/arXiv-2601.21015-b31b1b.svg)](https://arxiv.org/abs/2601.21015)

This is the **official implementation** of **MadAgents**.

- 📄 Paper: [arXiv:2601.21015](https://arxiv.org/abs/2601.21015)
- 📦 Supplementary material: `supplementary/`

---

## What can I do with MadAgents?

MadAgents is a set of **communicative agents** that support **MadGraph-centered HEP workflows**, including:

- **Install & configure** complex HEP toolchains
- **Teach & guide** users with step-by-step, executable instructions
- **Answer physics + implementation questions** and translate them into runnable workflows  
- **Run autonomous multi-step campaigns** and organize outputs + logs

---

## Quick start

### 0) Requirements

- **Linux host** (or a Linux VM on Windows/macOS, see [Install Apptainer](#install-apptainer))
- **Apptainer** installed on the host (see [Install Apptainer](#install-apptainer))
- **OpenAI API key** (currently the only supported provider)
- **Network access** to OpenAI endpoints

### 1) Get the code

Clone or download this repository.

### 2) Configure

Copy `config.env.example` to `config.env` in the repo root, then edit:

```dotenv
LLM_API_KEY="your-openai-key"
APPTAINER_DIR="/path/to/apptainer/bin"
```

> **WARNING:** Do **not** commit real keys. Keep `config.env` local and git-ignored.

### 3) Build image + overlay

```bash
# Preinstalled MadGraph stack (ROOT, Pythia8, Delphes)
./image/create_image.sh --type preinstall

# Clean base image (no preinstalled tools)
./image/create_image.sh --type clean
```

Creates:
- `image/madagents.sif` (Apptainer image)
- `image/mad_overlay.img` (overlay; persists container-side changes across runs)

### 4) Run

```bash
./madrun.sh
```

By default, the output is written to `./output` in the repository root.

`madrun.sh` handles cleanup on exit. `madrun_cleanup.sh` is an optional cleanup helper you can run at any time, but it is usually unnecessary unless a run is stuck or your terminal died:

```bash
./madrun_cleanup.sh
```

---

## Startup output (what you should see)

When you run `./madrun.sh`, the CLI should look like:

```
Starting MadAgents ...
Backend: http://127.0.0.1:8000
Frontend: http://127.0.0.1:5173
Apptainer>
```

If you don’t see this output, check out [Troubleshooting](#troubleshooting).

---

## Install Apptainer

We use **Apptainer** because it can *often* be installed and used **without sudo** (rootless / unprivileged), which is especially convenient on **HPC / computing clusters** where users typically do not have administrator rights.

Please follow the official documentation:
- **Official installation guide (all methods):** https://apptainer.org/docs/admin/main/installation.html
- **No-sudo (unprivileged) installation:** https://apptainer.org/docs/admin/main/installation.html#install-unprivileged-from-pre-built-binaries

On **Windows** and **macOS**, Apptainer does not run natively; you’ll need a **Linux VM** (recommended: **WSL2** on Windows, **Lima** on macOS):
- https://apptainer.org/docs/admin/main/installation.html#installation-on-windows-or-mac

If installation is **not possible in your environment** (e.g., required kernel features are disabled or local policy restricts installs), please contact your **cluster/system administrator** and request a site-wide Apptainer installation or the required system features.

---

## Configuration

All scripts read `config.env` from the repo root. Relative paths are resolved from the repo root.
Use `config.env.example` as the template if `config.env` is missing.

Model defaults:
- Agents use GPT‑5.1 models by default, except the Plan‑Updater which uses GPT‑5‑mini.
- You can change all model selections from the UI.

### Required

- `LLM_API_KEY` — OpenAI API key used by the agents (**only OpenAI models are supported**).
- `APPTAINER_DIR` — directory containing the `apptainer` binary (required by `image/create_image.sh`).

### Optional (defaults shown)

- `OUTPUT_DIR` — outputs folder (`output`)
- `RUN_DIR` — runtime folder for logs, locks, sockets (`run_dir`)
- `FRONTEND_PORT` — UI port (`5173`)
- `BACKEND_PORT` — API port (`8000`)
- `APPTAINER_CACHEDIR` — Apptainer cache (`.apptainer/cache`)
- `APPTAINER_CONFIGDIR` — Apptainer config (`.apptainer`)
- `NPM_CONFIG_CACHE` — npm cache (`.npm`)

### Minimal example

```dotenv
LLM_API_KEY="your-openai-key-here"
APPTAINER_DIR="/path/to/apptainer"
```

### Temporary overrides (CLI)

You can override values from `config.env` for a single run by passing flags to `madrun.sh`:

```bash
./madrun.sh --frontend_port 5173 --backend_port 8000
./madrun.sh --output_dir /tmp/madagents_out --run_dir /tmp/madagents_run
```

Run `./madrun.sh --help` for the full list of supported flags.

---

## Build image

All image definitions and build scripts live in `image/`.

```bash
./image/create_image.sh --type TYPE
```

Two image variants are supported:

- **`--type preinstall`** builds from `image/madagents_preinstall.def` and includes a **basic MadGraph stack**
  (ROOT, Pythia8, Delphes). The build downloads two tarballs; if the upstream links change, you may need
  to update them in the definition file.
- **`--type clean`** builds from `image/madagents_clean.def` and includes **no preinstalled tools**.

Both options create `image/madagents.sif` and `image/mad_overlay.img` (default size ~10GB), overwriting
any existing files with the same names.

**Notes**
- The build uses `apptainer build --fakeroot`. If your system disallows fakeroot, see
  [Troubleshooting](#troubleshooting).
- If you only need to rebuild the overlay, run:

```bash
./image/create_overlay.sh
```

---

## Stop / cleanup

`madrun.sh` traps exit signals and stops the Apptainer instance for you.
`madrun_cleanup.sh` is safe to run at any time, but it is usually unnecessary unless the process is wedged or your terminal died:

```bash
./madrun_cleanup.sh
```

Manual fallback:

```bash
apptainer instance list
apptainer instance stop INSTANCE_NAME
```

The `INSTANCE_NAME` is recorded in `run_dir/logs/instance_name.txt` and is usually `madagents`.

---

## Data, outputs, and persistence

- `OUTPUT_DIR` is where runtime outputs are written.
- `RUN_DIR` holds logs, locks, and instance metadata and can be deleted when you are done.
- The container is launched with an overlay (`image/mad_overlay.img`) so changes inside the container
  persist across runs until you rebuild or delete the overlay.

Want a “clean slate” run?
1. Stop the instance (`./madrun_cleanup.sh`)
2. Delete the overlay (`rm image/mad_overlay.img`)
3. Recreate it (`./image/create_overlay.sh`), and optionally rebuild the `.sif`

---

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| `config.env not found` | Run commands from the repo root or copy `config.env.example` to `config.env`. |
| `apptainer not found` | Install Apptainer or set `APPTAINER_DIR` in `config.env`. |
| `port already in use` | Choose free ports via `--frontend_port` / `--backend_port`. |
| Build fails | Ensure Apptainer supports `--fakeroot` and you have permissions to use it. |
| Preinstall build fails | The tarball download URLs in `image/madagents_preinstall.def` may have changed; update them and retry. |
| `cannot check port availability` | Install `ss`, `lsof`, or `python` so the script can test ports. |
| No UI link printed | Check `run_dir/logs/madagents_links.txt` and `run_dir/logs/madrun.log`. |
| UI not reachable from your browser | If running on a cluster or remote machine, you must **port‑forward** the backend and frontend ports (see `port_forward.sh`). |

### Multiple runs

MadAgents supports **one run per clone**. For multiple runs, **clone the repo multiple times** and
use **different ports** for each run. See [Temporary overrides (CLI)](#temporary-overrides-cli) for
how to set `--frontend_port` and `--backend_port`.

### Port forwarding (remote / cluster)

If you run MadAgents on a **remote machine or cluster**, the UI will not be reachable from your
local browser until you **port‑forward** the backend and frontend ports.

This repo includes a helper script: `port_forward.sh`.

1) Edit `port_forward.sh` and set `SSH_TARGET` to your SSH destination, e.g.:

```bash
SSH_TARGET="user@remote-host"
```

2) Run the script **from your local machine (the one with the browser)** and pass the ports you
need to forward:

```bash
./port_forward.sh --port 8000,5173
```

3) Open the UI locally in your browser:
`http://127.0.0.1:5173`

If you changed ports via `--frontend_port` / `--backend_port`, pass those same ports to
`port_forward.sh`.

### Cluster / HPC notes (build troubleshooting)

Apptainer is commonly used on clusters because **running containers does not require sudo** once installed.
Installation itself may still require admin help.

**If `--fakeroot` works**  
✅ Build normally with `./image/create_image.sh`.

**If `--fakeroot` is not allowed**  
Typical options:
1. **Use a prebuilt `.sif`**: build on a machine that supports fakeroot and distribute the image
   (e.g. GitHub Releases or a shared cluster filesystem).
2. Ask admins about enabling user namespaces / fakeroot (policy-dependent).

---

## Security

- `config.env` contains secrets (OpenAI API key). Treat it like a password.
- `config.env.example` is a safe template and can be committed.
- Do not commit real keys to version control.
- Logs may contain request metadata; store them appropriately.

---

## Citation

If you used MadAgents in your research, please cite us as follows:

```bibtex
@article{Plehn:2026gxv,
    author = "Plehn, Tilman and Schiller, Daniel and Schmal, Nikita",
    title = "{MadAgents}",
    eprint = "2601.21015",
    archivePrefix = "arXiv",
    primaryClass = "hep-ph",
    month = "1",
    year = "2026"
}
```
