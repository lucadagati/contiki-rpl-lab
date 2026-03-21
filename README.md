# RPL Lab with Contiki-NG + Renode

Simple, reproducible lab toolkit for testing RPL behavior with the `examples/rpl-udp` scenario in Contiki-NG.

This repository provides:
- the original slide deck (`lab - RPL.pdf`, `lab - RPL.pptx`)
- an interactive runner to automate Renode experiments
- a Docker-based Renode demo (no local Renode install required)
- a parser to summarize `Tx/Rx/MissedTx` logs into useful metrics

---

## 1) What you can do with this repo

- Run a **baseline** RPL scenario (1 server + 2 clients)
- Run a **range experiment** (`wireless SetRangeWirelessFunction`)
- Save run logs in a reproducible folder structure
- Compute summary metrics:
  - `PDR = Rx / Tx`
  - `MissRate = MissedTx / Tx`

---

## 2) Requirements

You need these tools installed on your machine:
- Python 3.9+
- Git
- Renode (available from official Renode releases) OR Docker
- Contiki-NG toolchain able to build `TARGET=cc2538dk`

Important:
- This repo **includes** the `contiki-ng/` source tree (vendored).
- After cloning this repo, you already have `contiki-ng/examples/rpl-udp`.

---

## 3) Files in this repo

- `run_rpl_lab_interactive.py`  
  Interactive runner that:
  1. generates `.resc` scripts inside `contiki-ng/examples/rpl-udp/`
  2. runs `make renode TARGET=cc2538dk SCRIPT=<generated>.resc`
  3. stores logs in `rpl_lab_runs/`

- `parse_rpl_udp_logs.py`  
  Parser for Contiki log lines:
  - per-node logs (`client-1.log`, `client-2.log`, ...)
  - combined single log (`--combined`)
  - fallback parsing from request/response lines when `Tx/Rx/MissedTx` snapshots are not present yet

- `run_renode_container_demo.sh` and `rpl-container-demo.resc`  
  Non-interactive Docker demo:
  - starts Renode in a container
  - runs a 30-second virtual-time RPL scenario
  - stores log in `demo-runs/container-demo.log`
  - parses summary automatically

- `rpl_story_demo.py`  
  Small presentation-friendly demo that explains RPL behavior in 4 steps:
  1) bootstrap (not reachable),
  2) convergence (sending requests),
  3) forwarding (server receives),
  4) end-to-end response (clients receive replies).

- `lab - RPL.pdf` / `lab - RPL.pptx`  
  Original lab deck (source material).

---

## 4) Quick start (end-to-end)

### Step A - Verify bundled Contiki-NG

Make sure this path exists in this repo:
- `./contiki-ng/examples/rpl-udp`

### Step B - Baseline run

From this repository folder:

```bash
python3 run_rpl_lab_interactive.py \
  --contiki-path /absolute/path/to/this-repo/contiki-ng \
  --mode baseline \
  --run-seconds 90
```

This generates a baseline `.resc` script and starts Renode via `make`.

### Step C - Parse baseline results

```bash
python3 parse_rpl_udp_logs.py --combined /absolute/path/to/rpl_lab_runs/baseline_range11.log
```

Output includes:
- number of snapshots found
- average PDR / MissRate
- last snapshot values

---

## 5) Docker demo (no local Renode required)

If you want a fully containerized demo run:

```bash
./run_renode_container_demo.sh
```

What it does:
1. uses `antmicro/renode:latest`
2. runs `rpl-container-demo.resc` in console/headless mode
3. saves logs to `demo-runs/container-demo.log`
4. prints a parsed summary via `parse_rpl_udp_logs.py`

Example output:
- `client-1  Tx=6  Rx=6  Missed=2  PDR=1.0000`
- `client-2  Tx=6  Rx=6  Missed=2  PDR=1.0000`

Notes:
- On some macOS Docker setups, mounting from `/Users/...` is restricted.  
  The script handles this by copying the `.resc` file to `/tmp` before running Docker.

---

## 6) Range experiment (reproducible)

Run multiple range values:

```bash
python3 run_rpl_lab_interactive.py \
  --contiki-path /absolute/path/to/this-repo/contiki-ng \
  --mode range \
  --ranges 5,8,11,14 \
  --run-seconds 90
```

Then parse each generated log:

```bash
python3 parse_rpl_udp_logs.py --combined /absolute/path/to/rpl_lab_runs/range5.log
python3 parse_rpl_udp_logs.py --combined /absolute/path/to/rpl_lab_runs/range8.log
python3 parse_rpl_udp_logs.py --combined /absolute/path/to/rpl_lab_runs/range11.log
python3 parse_rpl_udp_logs.py --combined /absolute/path/to/rpl_lab_runs/range14.log
```

Recommended report table:
- columns: `Range`, `AvgPDR`, `AvgMissRate`, `LastSnapshotPDR`

---

## 7) Mini protocol demo (for class presentation)

Single command:

```bash
python3 rpl_story_demo.py --run
```

It will:
1. execute the container demo (`run_renode_container_demo.sh`)
2. analyze the generated log
3. print a short human-readable RPL story with counters and estimated PDR

If you already have a log:

```bash
python3 rpl_story_demo.py --log demo-runs/container-demo.log
```

---

## 8) Dry-run mode (no Renode required)

To test workflow and script generation without launching Renode:

```bash
python3 run_rpl_lab_interactive.py \
  --contiki-path /absolute/path/to/this-repo/contiki-ng \
  --mode range \
  --ranges 5,11 \
  --dry-run
```

This verifies:
- path checks
- script generation
- command orchestration

---

## 9) Parser usage

### A) Per-node logs

If you store logs as:
- `logs/client-1.log`
- `logs/client-2.log`

Run:

```bash
python3 parse_rpl_udp_logs.py logs --glob "client-*.log"
```

### B) Combined run log

```bash
python3 parse_rpl_udp_logs.py --combined /path/to/run.log
```

---

## 10) Troubleshooting

- `renode: command not found`  
  Install Renode or make sure it is in your shell `PATH`.

- `Cannot find: .../examples/rpl-udp`  
  Check `--contiki-path` and ensure it points to the root of your `contiki-ng` clone.

- No `Tx/Rx/MissedTx` lines found  
  Let the simulation run longer (`--run-seconds 120`) and confirm nodes are producing output.
  The parser can still compute fallback metrics from `Sending request` / `Received response` lines in combined logs.

---

## 11) Reproducibility checklist

For each run, save:
- Renode version (`renode -v`)
- Contiki-NG commit (`git -C /path/to/contiki-ng rev-parse HEAD`)
- target (`cc2538dk`)
- mode (`baseline` or `range`)
- range values used
- run duration

This makes the experiment repeatable across machines.

