#!/usr/bin/env python3
"""
Small storytelling demo for RPL behavior using container logs.

It can:
1) run the container demo script (optional)
2) parse the combined log
3) print a short, human-friendly timeline of RPL phases
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass


LINE_RE = re.compile(r"\[INFO\]\s+(client-\d+|server)/uart0:.*\[(INFO: App\s*)\]\s+(.*)")


@dataclass
class Counters:
    not_reachable: int = 0
    sent: int = 0
    recv_at_server: int = 0
    recv_response: int = 0


def analyze_log(log_path: str) -> dict[str, Counters]:
    counters: dict[str, Counters] = {
        "client-1": Counters(),
        "client-2": Counters(),
        "server": Counters(),
    }

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = LINE_RE.search(line)
            if not m:
                continue

            node = m.group(1)
            msg = m.group(3)
            counters.setdefault(node, Counters())

            if "Not reachable yet" in msg and node.startswith("client-"):
                counters[node].not_reachable += 1
            elif "Sending request" in msg and node.startswith("client-"):
                counters[node].sent += 1
            elif "Received request" in msg and node == "server":
                counters[node].recv_at_server += 1
            elif "Received response" in msg and node.startswith("client-"):
                counters[node].recv_response += 1

    return counters


def print_story(counters: dict[str, Counters]) -> None:
    c1 = counters.get("client-1", Counters())
    c2 = counters.get("client-2", Counters())
    srv = counters.get("server", Counters())

    print("=== RPL Mini Demo: What happened ===")
    print("1) Bootstrap phase")
    print(
        f"   - Clients initially not reachable -> client-1={c1.not_reachable}, "
        f"client-2={c2.not_reachable}"
    )
    print("2) Convergence phase")
    print(
        f"   - Clients start sending UDP over RPL -> client-1 sent={c1.sent}, "
        f"client-2 sent={c2.sent}"
    )
    print("3) Data forwarding")
    print(f"   - Server receives client requests -> server received={srv.recv_at_server}")
    print("4) End-to-end response")
    print(
        f"   - Clients receive echo responses -> client-1 rx={c1.recv_response}, "
        f"client-2 rx={c2.recv_response}"
    )

    total_sent = c1.sent + c2.sent
    total_rx = c1.recv_response + c2.recv_response
    pdr = (total_rx / total_sent) if total_sent else 0.0
    print(f"\nEstimated end-to-end PDR (from request/response lines): {pdr:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log",
        default="demo-runs/container-demo.log",
        help="Combined log path (default: demo-runs/container-demo.log)",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run the container demo before analyzing the log.",
    )
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(repo_root, args.log) if not os.path.isabs(args.log) else args.log

    if args.run:
        script_path = os.path.join(repo_root, "run_renode_container_demo.sh")
        subprocess.run([script_path], check=True)

    if not os.path.exists(log_path):
        raise SystemExit(f"Log file not found: {log_path}. Run with --run first.")

    counters = analyze_log(log_path)
    print_story(counters)


if __name__ == "__main__":
    main()

