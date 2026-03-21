#!/usr/bin/env python3
"""
Interactive runner for the RPL (rpl-udp) Renode lab.

This script:
1) Generates Renode .resc scripts in <contiki-ng>/examples/rpl-udp/
2) Runs "make renode TARGET=cc2538dk SCRIPT=<generated>.resc" for each configuration
3) Saves stdout/stderr into a run log file

It is interactive by default: you press Enter to stop a run once you collected
enough "Tx/Rx/MissedTx" lines.

Notes:
- This script cannot auto-extract per-node logs from Renode windows; it saves the
  combined console output. For per-node extraction, capture each node window output separately.
- The combined log parser is supported by parse_rpl_udp_logs.py --combined.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


CLIENT_POSITIONS = [
    (10, 0, 0),    # client-1
    (0, 10, 0),    # client-2
    (-10, 0, 0),   # client-3
    (0, -10, 0),   # client-4
]


def generate_range_resc(range_value: int, dist: int = 10) -> str:
    # Keep this script minimal and deterministic.
    return f""":name: cc2538 rpl-udp range {range_value}

emulation CreateIEEE802_15_4Medium "wireless"

$range = {range_value}
$dist  = {dist}

wireless SetRangeWirelessFunction $range

######################### UDP SERVER - begin #########################
$bin=@build/cc2538dk/udp-server.cc2538dk
$name="server"
i @scripts/single-node/cc2538.resc
connector Connect radio wireless
wireless SetPosition radio 0 0 0
mach clear
########################## UDP SERVER - end ##########################

######################### UDP CLIENT - begin #########################
$bin=@build/cc2538dk/udp-client.cc2538dk
$name="client-1"
i @scripts/single-node/cc2538.resc
connector Connect radio wireless
wireless SetPosition radio $dist 0 0
mach clear
########################## UDP CLIENT - end ##########################

######################### UDP CLIENT - begin #########################
$name="client-2"
i @scripts/single-node/cc2538.resc
connector Connect radio wireless
wireless SetPosition radio 0 $dist 0
mach clear
########################## UDP CLIENT - end ##########################
"""


def generate_nclients_resc(nclients: int, range_value: int = 11, dist: int = 10) -> str:
    if not (1 <= nclients <= 4):
        raise ValueError("nclients must be in [1..4]")

    lines: list[str] = []
    lines.append(f""":name: cc2538 rpl-udp {nclients} clients range {range_value}

emulation CreateIEEE802_15_4Medium "wireless"

$range = {range_value}
$dist  = {dist}

wireless SetRangeWirelessFunction $range

######################### UDP SERVER - begin #########################
$bin=@build/cc2538dk/udp-server.cc2538dk
$name="server"
i @scripts/single-node/cc2538.resc
connector Connect radio wireless
wireless SetPosition radio 0 0 0
mach clear
########################## UDP SERVER - end ##########################
""")

    positions = CLIENT_POSITIONS[:nclients]
    for idx, (x, y, z) in enumerate(positions, start=1):
        lines.append(
            f"""######################### UDP CLIENT - begin #########################
$bin=@build/cc2538dk/udp-client.cc2538dk
$name="client-{idx}"
i @scripts/single-node/cc2538.resc
connector Connect radio wireless
wireless SetPosition radio {x} {y} {z}
mach clear
########################## UDP CLIENT - end ##########################
"""
        )

    return "\n".join(lines)


def ensure_renode_available() -> None:
    # We don't hard-fail if renode is missing because some environments call it via an alias inside make.
    if subprocess.call(["sh", "-lc", "command -v renode >/dev/null 2>&1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        print("Warning: 'renode' command not found in PATH.", file=sys.stderr)


def run_make_renode(
    *,
    contiki_examples_dir: Path,
    script_name: str,
    target: str,
    run_log_path: Path,
    run_seconds: int | None,
) -> None:
    cmd = [
        "make",
        "renode",
        f"TARGET={target}",
        f"SCRIPT={script_name}",
    ]

    print(f"Running: {' '.join(cmd)}")
    print(f"Logging to: {run_log_path}")

    with run_log_path.open("w", encoding="utf-8") as f:
        proc = subprocess.Popen(
            cmd,
            cwd=str(contiki_examples_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert proc.stdout is not None

        def reader() -> None:
            for line in proc.stdout:  # type: ignore[assignment]
                f.write(line)
                f.flush()
                print(line, end="")

        t = threading.Thread(target=reader, daemon=True)
        t.start()

        if run_seconds is not None:
            time.sleep(run_seconds)
            proc.send_signal(signal.SIGINT)
        else:
            input("Press Enter to stop this run once you collected enough Tx/Rx/MissedTx lines...")
            proc.send_signal(signal.SIGINT)

        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contiki-path", help="Path to the contiki-ng repo (the one containing examples/rpl-udp).")
    parser.add_argument("--target", default="cc2538dk", help="Contiki target (default: cc2538dk).")
    parser.add_argument("--out-dir", default="rpl_lab_runs", help="Where to store logs and generated scripts (default: rpl_lab_runs).")
    parser.add_argument("--mode", choices=["baseline", "range"], default="baseline", help="Lab mode (default: baseline).")
    parser.add_argument("--ranges", default="5,8,11,14", help="Comma-separated range list for --mode range.")
    parser.add_argument("--nclients", default="2,3,4", help="Comma-separated N list for future extensions.")
    parser.add_argument("--run-seconds", type=int, default=90, help="Auto-stop each run after N seconds (default: 90). Use 0 to wait for Enter.")
    parser.add_argument("--dry-run", action="store_true", help="Generate scripts only; do not run make/renode.")
    args = parser.parse_args()

    ensure_renode_available()

    contiki_path = Path(args.contiki_path) if args.contiki_path else None
    if contiki_path is None:
        contiki_path = Path(input("Path to contiki-ng repo: ").strip())

    contiki_examples_dir = contiki_path / "examples" / "rpl-udp"
    if not contiki_examples_dir.exists():
        raise SystemExit(f"Cannot find: {contiki_examples_dir}")

    out_dir = Path(args.out_dir).absolute()
    out_dir.mkdir(parents=True, exist_ok=True)

    script_dir = contiki_examples_dir  # Renode scripts passed via make are resolved there in most setups.

    run_seconds: int | None = None if args.run_seconds == 0 else args.run_seconds

    if args.mode == "baseline":
        # Baseline: just run the default-ish scenario via generated script.
        range_value = 11
        script_name = "rpl-udp-lab-baseline.resc"
        (script_dir / script_name).write_text(generate_range_resc(range_value), encoding="utf-8")
        log_path = out_dir / f"baseline_range{range_value}.log"
        if args.dry_run:
            print("Dry run: generated script only (no execution).")
            print(f"  Script: {script_dir / script_name}")
            print(f"  Would log to: {log_path}")
        else:
            run_make_renode(
                contiki_examples_dir=contiki_examples_dir,
                script_name=script_name,
                target=args.target,
                run_log_path=log_path,
                run_seconds=run_seconds,
            )
        print("Run finished. To summarize logs:")
        print(f"  python3 parse_rpl_udp_logs.py --combined '{log_path}'")
        return

    if args.mode == "range":
        ranges = [int(x.strip()) for x in args.ranges.split(",") if x.strip()]
        for r in ranges:
            script_name = f"rpl-udp-lab-range-{r}.resc"
            (script_dir / script_name).write_text(generate_range_resc(r), encoding="utf-8")
            log_path = out_dir / f"range{r}.log"
            if args.dry_run:
                print(f"Dry run: generated script only for range={r} (no execution).")
                print(f"  Script: {script_dir / script_name}")
                print(f"  Would log to: {log_path}")
            else:
                run_make_renode(
                    contiki_examples_dir=contiki_examples_dir,
                    script_name=script_name,
                    target=args.target,
                    run_log_path=log_path,
                    run_seconds=run_seconds,
                )
            print(f"Parsed summary for range={r}:")
            print(f"  python3 parse_rpl_udp_logs.py --combined '{log_path}'")
        return

    raise SystemExit(f"Unsupported mode: {args.mode}")


if __name__ == "__main__":
    main()

