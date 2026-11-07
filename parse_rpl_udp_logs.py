#!/usr/bin/env python3
"""
Parse Contiki-NG rpl-udp client logs.

Expected log line pattern (from examples/rpl-udp/udp-client.c):
  Tx/Rx/MissedTx: <tx>/<rx>/<missed>

Usage:
  1) Per-node logs (directory with client-1.log, client-2.log, ...):
     python3 parse_rpl_udp_logs.py /path/to/logs/

  2) Combined log (a single file with all lines, not split per node):
     python3 parse_rpl_udp_logs.py --combined /path/to/run.log

Where `logs/` contains files like:
  client-1.log
  client-2.log
  ...
"""

from __future__ import annotations

import argparse
import glob
import os
import re
from dataclasses import dataclass
from typing import Optional


TXRX_MISSED_RE = re.compile(r"Tx/Rx/MissedTx:\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
CLIENT_SENDING_REQ_RE = re.compile(r"client-(\d+)/uart0:.*Sending request", re.IGNORECASE)
CLIENT_RECEIVED_RESP_RE = re.compile(r"client-(\d+)/uart0:.*Received response", re.IGNORECASE)
CLIENT_NOT_REACHABLE_RE = re.compile(r"client-(\d+)/uart0:.*Not reachable yet", re.IGNORECASE)


@dataclass
class Stats:
    tx: int
    rx: int
    missed: int

    @property
    def pdr(self) -> float:
        return self.rx / self.tx if self.tx else 0.0

    @property
    def miss_rate(self) -> float:
        return self.missed / self.tx if self.tx else 0.0


def parse_last_stats(path: str) -> Optional[Stats]:
    last: Optional[Stats] = None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = TXRX_MISSED_RE.search(line)
                if not m:
                    continue
                tx, rx, missed = map(int, m.groups())
                last = Stats(tx=tx, rx=rx, missed=missed)
    except FileNotFoundError:
        return None
    return last


def parse_all_stats(path: str) -> list[Stats]:
    stats: list[Stats] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = TXRX_MISSED_RE.search(line)
            if not m:
                continue
            tx, rx, missed = map(int, m.groups())
            stats.append(Stats(tx=tx, rx=rx, missed=missed))
    return stats


def print_combined_summary(path: str) -> None:
    stats = parse_all_stats(path)
    if not stats:
        # Fallback path for runs where stats snapshots are not printed yet:
        # estimate Tx/Rx/Missed from "Sending request", "Received response",
        # "Not reachable yet" lines per client.
        by_client: dict[str, dict[str, int]] = {}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m_send = CLIENT_SENDING_REQ_RE.search(line)
                if m_send:
                    c = f"client-{m_send.group(1)}"
                    by_client.setdefault(c, {"tx": 0, "rx": 0, "missed": 0})
                    by_client[c]["tx"] += 1
                    continue

                m_recv = CLIENT_RECEIVED_RESP_RE.search(line)
                if m_recv:
                    c = f"client-{m_recv.group(1)}"
                    by_client.setdefault(c, {"tx": 0, "rx": 0, "missed": 0})
                    by_client[c]["rx"] += 1
                    continue

                m_miss = CLIENT_NOT_REACHABLE_RE.search(line)
                if m_miss:
                    c = f"client-{m_miss.group(1)}"
                    by_client.setdefault(c, {"tx": 0, "rx": 0, "missed": 0})
                    by_client[c]["missed"] += 1

        if not by_client:
            raise SystemExit(
                f"No stats lines and no request/response fallback lines found in: {path}"
            )

        print("Combined run summary (fallback from request/response lines)")
        print("Node\tTx\tRx\tMissed\tPDR\tMissRate")
        all_stats: list[Stats] = []
        for client in sorted(by_client):
            s = Stats(
                tx=by_client[client]["tx"],
                rx=by_client[client]["rx"],
                missed=by_client[client]["missed"],
            )
            all_stats.append(s)
            print(f"{client}\t{s.tx}\t{s.rx}\t{s.missed}\t{s.pdr:.4f}\t{s.miss_rate:.4f}")

        avg_pdr = sum(s.pdr for s in all_stats) / len(all_stats)
        avg_miss_rate = sum(s.miss_rate for s in all_stats) / len(all_stats)
        print(f"AvgPDR: {avg_pdr:.4f}")
        print(f"AvgMissRate: {avg_miss_rate:.4f}")
        return

    # Simple aggregation: average over all observed snapshots.
    avg_pdr = sum(s.pdr for s in stats) / len(stats)
    avg_miss_rate = sum(s.miss_rate for s in stats) / len(stats)

    last = stats[-1]
    print("Combined run summary")
    print(f"Snapshots found: {len(stats)}")
    print(f"AvgPDR: {avg_pdr:.4f}")
    print(f"AvgMissRate: {avg_miss_rate:.4f}")
    print(f"LastSnapshot -> Tx={last.tx}, Rx={last.rx}, Missed={last.missed}, "
          f"PDR={last.pdr:.4f}, MissRate={last.miss_rate:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log_dir", nargs="?", help="Directory containing per-node log files (e.g. client-1.log).")
    parser.add_argument("--glob", default="*.log", help="Glob pattern inside log_dir (default: *.log).")
    parser.add_argument("--combined", help="Parse a single combined log file (e.g. run.log).")
    args = parser.parse_args()

    if args.combined:
        print_combined_summary(os.path.abspath(args.combined))
        return

    if not args.log_dir:
        raise SystemExit("Either provide log_dir (per-node logs) or use --combined <file>.")

    log_dir = os.path.abspath(args.log_dir)
    pattern = os.path.join(log_dir, args.glob)
    paths = sorted(glob.glob(pattern))

    if not paths:
        raise SystemExit(f"No log files matched: {pattern}")

    rows = []
    for p in paths:
        stats = parse_last_stats(p)
        if stats is None:
            continue
        node = os.path.splitext(os.path.basename(p))[0]
        rows.append((node, stats))

    if not rows:
        raise SystemExit(f"Matched files, but no 'Tx/Rx/MissedTx' lines found under: {log_dir}")

    print("Node\tTx\tRx\tMissed\tPDR\tMissRate")
    for node, s in rows:
        print(
            f"{node}\t{s.tx}\t{s.rx}\t{s.missed}\t{s.pdr:.4f}\t{s.miss_rate:.4f}"
        )


if __name__ == "__main__":
    main()

