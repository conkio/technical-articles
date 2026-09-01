#!/usr/bin/env python3
"""Generate the data-driven figures used by the CPU cores/threads article.

Inputs:
    data/processed/sysbench_scaling.csv
    data/processed/7zip_scaling.csv

Outputs:
    figures/sysbench-throughput.png
    figures/7zip-rating.png

Generate the CSV files first with:
    python3 analysis/parse_results.py

Dependency:
    matplotlib
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import StrMethodFormatter
except ImportError:
    print(
        "ERROR: matplotlib is required. Install it with "
        "'python3 -m pip install matplotlib'.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def means_from_csv(path: Path, value_field: str):
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; run analysis/parse_results.py first")

    grouped = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"threads", value_field}.issubset(reader.fieldnames):
            raise ValueError(f"{path}: missing required CSV columns")
        for row in reader:
            grouped.setdefault(int(row["threads"]), []).append(float(row[value_field]))

    if set(grouped) != set(range(1, 13)):
        raise ValueError(f"{path}: expected thread counts 1-12; found {sorted(grouped)}")

    threads = sorted(grouped)
    means = [statistics.mean(grouped[t]) for t in threads]
    return threads, means


def mark_cpu_transition(ax) -> None:
    # 1-6 threads use one hardware thread from each physical core.
    # 7-12 progressively add the second hardware thread from those cores.
    ax.axvline(6.5, linestyle="--", linewidth=1)
    ax.text(3.5, 0.96, "Physical cores added", transform=ax.get_xaxis_transform(),
            ha="center", va="top")
    ax.text(9.5, 0.96, "Additional hardware threads", transform=ax.get_xaxis_transform(),
            ha="center", va="top")


def line_figure(threads, values, title, ylabel, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(threads, values, marker="o", linewidth=1.8)
    mark_cpu_transition(ax)
    ax.set_title(title)
    ax.set_xlabel("Benchmark threads")
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(1, 13))
    ax.set_xlim(0.7, 12.3)
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.grid(axis="y", alpha=0.25)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate benchmark figures from processed CSV data.")
    ap.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root; defaults to the parent of analysis/",
    )
    args = ap.parse_args()

    root = args.project_root.resolve()
    processed = root / "data" / "processed"
    figures = root / "figures"

    try:
        threads, values = means_from_csv(processed / "sysbench_scaling.csv", "events_per_second")
        line_figure(
            threads,
            values,
            "sysbench CPU throughput by thread count",
            "Mean events per second",
            figures / "sysbench-throughput.png",
        )

        threads, values = means_from_csv(processed / "7zip_scaling.csv", "total_rating")
        line_figure(
            threads,
            values,
            "7-Zip total rating by thread count",
            "Mean total rating (MIPS)",
            figures / "7zip-rating.png",
        )

    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {figures / 'sysbench-throughput.png'}")
    print(f"Generated {figures / '7zip-rating.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
