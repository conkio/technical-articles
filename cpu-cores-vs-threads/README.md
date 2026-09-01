# CPU Cores vs Threads: Theory, SMT, and Benchmark Performance

This repository contains the article, benchmark scripts, raw benchmark
output, processed results, and supporting figures for an examination of
physical CPU cores and Simultaneous Multi-Threading (SMT).

The benchmarks compare scaling across physical cores and additional hardware
threads provided by SMT, using both sysbench and the 7-Zip built-in benchmark.

## Repository contents

- [`article/`](article/) — full article in Markdown and PDF format
- [`scripts/`](scripts/) — scripts used to run the benchmark tests
- [`data/raw/`](data/raw/) — original benchmark output and CPU validation logs
- [`data/processed/`](data/processed/) — CSV data extracted from the raw results
- [`analysis/`](analysis/) — Python scripts used to process results and generate figures
- [`figures/`](figures/) — figures used in the article
- [`data/environment.txt`](data/environment.txt) — hardware and software test environment
- [`REPRODUCING.md`](REPRODUCING.md) — instructions for reproducing the benchmarks and analysis

## Article

The full article is available here:

- [Markdown article](article/README.md)
- [PDF article](article/cpu-cores-vs-threads.pdf)

## Reproducing the results

See [REPRODUCING.md](REPRODUCING.md) for the complete procedure covering:

1. benchmark requirements;
2. CPU topology and affinity configuration;
3. running the sysbench and 7-Zip tests;
4. generating the processed CSV files;
5. regenerating the figures.

Exact benchmark values will vary between processors and systems. The
repository is intended to reproduce the test methodology and analysis
workflow used for the results presented in the article.