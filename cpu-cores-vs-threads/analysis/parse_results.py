#!/usr/bin/env python3
"""Parse raw sysbench and 7-Zip result files into reproducible CSV datasets.

Expected repository layout:

    data/raw/sysbench/
    data/raw/sysbench-topology/   # legacy name data/raw/topology/ is also accepted
    data/raw/7zip/
    data/raw/7zip-topology/
    data/processed/

Only top-level files ending in ``-result.txt`` are parsed. Master logs,
mpstat validation files, sanity checks, and operational marker files are ignored.

Usage:
    python3 analysis/parse_results.py

By default the script verifies that the complete published dataset is present:
12 scaling configurations x 5 repetitions and 2 topology configurations x 5
repetitions for each benchmark. Use --allow-partial only while testing.
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import sys
from pathlib import Path

EXPECTED_THREADS = set(range(1, 13))
EXPECTED_REPS = set(range(1, 6))
EXPECTED_TOPOLOGIES = {"6physical", "3physical-smt"}


class ParseError(RuntimeError):
    pass


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def required(pattern: str, source: str, label: str, path: Path) -> str:
    match = re.search(pattern, source, re.MULTILINE)
    if not match:
        raise ParseError(f"{path}: could not find {label}")
    return match.group(1).strip()


def optional(pattern: str, source: str):
    match = re.search(pattern, source, re.MULTILINE)
    return match.group(1).strip() if match else None


def repetition(path: Path) -> int:
    match = re.search(r"-r(\d+)-result\.txt$", path.name)
    if not match:
        raise ParseError(f"{path}: expected '-rN-result.txt' filename")
    return int(match.group(1))


def parse_sysbench(path: Path, topology_run: bool) -> dict:
    source = text(path)
    row = {
        "timestamp": required(r"^Timestamp:\s*(.+)$", source, "timestamp", path),
        "threads": int(required(r"^Threads:\s*(\d+)\s*$", source, "threads", path)),
        "repetition": repetition(path),
        "cpu_affinity": required(r"^CPU affinity:\s*(.+)$", source, "CPU affinity", path),
        "duration_seconds": int(required(r"^Duration:\s*(\d+)\s+seconds\s*$", source, "duration", path)),
        "prime_limit": int(required(r"^Prime limit:\s*(\d+)\s*$", source, "prime limit", path)),
        "events_per_second": float(required(
            r"^\s*events per second:\s*([0-9]+(?:\.[0-9]+)?)\s*$",
            source,
            "events per second",
            path,
        )),
        "source_file": path.name,
    }

    topology = optional(r"^Topology:\s*(.+)$", source)
    if topology_run:
        if not topology:
            raise ParseError(f"{path}: topology result has no Topology field")
        row["topology"] = topology
    elif topology:
        raise ParseError(f"{path}: scaling result unexpectedly contains Topology")

    return row


def parse_7zip(path: Path, topology_run: bool) -> dict:
    source = text(path)

    avr_lines = [line for line in source.splitlines() if line.lstrip().startswith("Avr:")]
    tot_lines = [line for line in source.splitlines() if line.lstrip().startswith("Tot:")]
    if not avr_lines or not tot_lines:
        raise ParseError(f"{path}: missing 7-Zip Avr/Tot summary")

    if "|" not in avr_lines[-1]:
        raise ParseError(f"{path}: malformed 7-Zip Avr line")

    left, right = avr_lines[-1].split("|", 1)
    left_numbers = re.findall(r"-?\d+(?:\.\d+)?", left)
    right_numbers = re.findall(r"-?\d+(?:\.\d+)?", right)
    total_numbers = re.findall(r"-?\d+(?:\.\d+)?", tot_lines[-1])
    if len(left_numbers) < 4 or len(right_numbers) < 4 or not total_numbers:
        raise ParseError(f"{path}: incomplete 7-Zip summary")

    row = {
        "timestamp": required(r"^Timestamp:\s*(.+)$", source, "timestamp", path),
        "threads": int(required(
            r"^(?:Threads requested|Threads):\s*(\d+)\s*$",
            source,
            "benchmark thread count",
            path,
        )),
        "repetition": repetition(path),
        "cpu_affinity": required(r"^CPU affinity:\s*(.+)$", source, "CPU affinity", path),
        "internal_iterations": int(required(
            r"^7-Zip internal iterations:\s*(\d+)\s*$",
            source,
            "7-Zip internal iterations",
            path,
        )),
        "compression_rating": float(left_numbers[-1]),
        "decompression_rating": float(right_numbers[-1]),
        "total_rating": float(total_numbers[-1]),
        "source_file": path.name,
    }

    topology = optional(r"^Topology:\s*(.+)$", source)
    if topology_run:
        if not topology:
            raise ParseError(f"{path}: topology result has no Topology field")
        row["topology"] = topology
    elif topology:
        raise ParseError(f"{path}: scaling result unexpectedly contains Topology")

    return row


def find_dir(raw_root: Path, *names: str) -> Path:
    matches = [raw_root / name for name in names if (raw_root / name).is_dir()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ParseError("raw-data directory not found: " + " or ".join(str(raw_root / n) for n in names))
    raise ParseError("multiple candidate raw-data directories found: " + ", ".join(map(str, matches)))


def parse_dir(directory: Path, parser, topology_run: bool) -> list[dict]:
    return [parser(path, topology_run) for path in sorted(directory.glob("*-result.txt"))]


def validate_scaling(rows: list[dict], label: str) -> None:
    keys = {(int(r["threads"]), int(r["repetition"])) for r in rows}
    expected = {(t, r) for t in EXPECTED_THREADS for r in EXPECTED_REPS}
    if len(rows) != len(keys):
        raise ParseError(f"{label}: duplicate thread/repetition result")
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        raise ParseError(f"{label}: dataset mismatch; missing={missing}, extra={extra}")


def validate_topology(rows: list[dict], label: str) -> None:
    keys = {(str(r["topology"]), int(r["repetition"])) for r in rows}
    expected = {(t, r) for t in EXPECTED_TOPOLOGIES for r in EXPECTED_REPS}
    if len(rows) != len(keys):
        raise ParseError(f"{label}: duplicate topology/repetition result")
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        raise ParseError(f"{label}: dataset mismatch; missing={missing}, extra={extra}")


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def show_summary(label: str, rows: list[dict], value_field: str, group_field: str) -> None:
    groups = {}
    for row in rows:
        groups.setdefault(row[group_field], []).append(float(row[value_field]))
    print(f"\n{label}")
    for group in sorted(groups, key=lambda x: (isinstance(x, str), x)):
        values = groups[group]
        mean = statistics.mean(values)
        sd = statistics.stdev(values) if len(values) > 1 else 0.0
        print(f"  {group}: mean={mean:.2f}, sd={sd:.2f}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse raw CPU benchmark results into CSV files.")
    ap.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root; defaults to the parent of analysis/",
    )
    ap.add_argument(
        "--allow-partial",
        action="store_true",
        help="skip complete-dataset validation (for parser testing only)",
    )
    args = ap.parse_args()

    root = args.project_root.resolve()
    raw = root / "data" / "raw"
    processed = root / "data" / "processed"

    try:
        sb = parse_dir(find_dir(raw, "sysbench"), parse_sysbench, False)
        sb_top = parse_dir(find_dir(raw, "sysbench-topology", "topology"), parse_sysbench, True)
        z7 = parse_dir(find_dir(raw, "7zip"), parse_7zip, False)
        z7_top = parse_dir(find_dir(raw, "7zip-topology"), parse_7zip, True)

        if not args.allow_partial:
            validate_scaling(sb, "sysbench scaling")
            validate_topology(sb_top, "sysbench topology")
            validate_scaling(z7, "7-Zip scaling")
            validate_topology(z7_top, "7-Zip topology")

        sb.sort(key=lambda r: (r["threads"], r["repetition"]))
        sb_top.sort(key=lambda r: (r["topology"], r["repetition"]))
        z7.sort(key=lambda r: (r["threads"], r["repetition"]))
        z7_top.sort(key=lambda r: (r["topology"], r["repetition"]))

        write_csv(processed / "sysbench_scaling.csv", [
            "timestamp", "threads", "repetition", "cpu_affinity", "duration_seconds",
            "prime_limit", "events_per_second", "source_file"
        ], sb)
        write_csv(processed / "sysbench_topology.csv", [
            "timestamp", "topology", "threads", "repetition", "cpu_affinity",
            "duration_seconds", "prime_limit", "events_per_second", "source_file"
        ], sb_top)
        write_csv(processed / "7zip_scaling.csv", [
            "timestamp", "threads", "repetition", "cpu_affinity", "internal_iterations",
            "compression_rating", "decompression_rating", "total_rating", "source_file"
        ], z7)
        write_csv(processed / "7zip_topology.csv", [
            "timestamp", "topology", "threads", "repetition", "cpu_affinity",
            "internal_iterations", "compression_rating", "decompression_rating",
            "total_rating", "source_file"
        ], z7_top)

        print(f"Wrote CSV files to {processed}")
        print(f"  sysbench scaling rows: {len(sb)}")
        print(f"  sysbench topology rows: {len(sb_top)}")
        print(f"  7-Zip scaling rows: {len(z7)}")
        print(f"  7-Zip topology rows: {len(z7_top)}")

        show_summary("sysbench scaling (events/sec)", sb, "events_per_second", "threads")
        show_summary("7-Zip scaling (total rating)", z7, "total_rating", "threads")
        show_summary("sysbench topology (events/sec)", sb_top, "events_per_second", "topology")
        show_summary("7-Zip topology (total rating)", z7_top, "total_rating", "topology")

    except ParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
