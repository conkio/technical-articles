# Reproducing the Benchmarks and Results

This repository contains the benchmark scripts, raw benchmark output,
processed CSV data, and figure-generation code used for the article.

The original test system is documented in
[`data/environment.txt`](data/environment.txt).

Exact numerical results will vary between processors and systems. The steps
below reproduce the benchmark methodology and the processing workflow used
for the results presented in the article.

## 1. Requirements

The benchmark scripts require:

- Linux
- Bash
- `taskset`
- `sysbench`
- 7-Zip (`7z`)
- `mpstat` from the `sysstat` package

The analysis scripts require:

- Python 3
- Matplotlib

On AlmaLinux, the benchmark tools can be installed using the appropriate
system packages. Python analysis can be kept isolated in a virtual
environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `python3 -m venv` is not available, install the required Python virtual
environment package for the operating system first.

## 2. Check the CPU topology

Before running the benchmarks, inspect the processor topology:

```bash
lscpu
lscpu -e=CPU,CORE,SOCKET,NODE
```

The original test system used an AMD EPYC 4244P with six physical cores and
two hardware threads per core, giving 12 logical CPUs.

The logical CPU pairs were:

```text
Core 0: CPUs 0,6
Core 1: CPUs 1,7
Core 2: CPUs 2,8
Core 3: CPUs 3,9
Core 4: CPUs 4,10
Core 5: CPUs 5,11
```

The supplied scripts use this layout for CPU affinity.

For the scaling tests, logical CPUs 0 through 5 are used first so that the
first six benchmark threads are placed on separate physical cores. Logical
CPUs 6 through 11 are then added progressively as the second hardware thread
from each core.

The topology comparison uses:

```text
Six physical cores, one hardware thread per core:
0,1,2,3,4,5

Three physical cores, both hardware threads per core:
0,6,1,7,2,8
```

If the tests are run on a processor with a different logical CPU layout, the
affinity mappings in the shell scripts must be changed to match that system.

## 3. Run the benchmark scripts

Run the scripts from the `cpu-cores-vs-threads` repository directory.

The recommended order is:

```bash
bash scripts/run_sysbench.sh
bash scripts/run_sysbench_topology.sh
bash scripts/run_7zip.sh
bash scripts/run_7zip_topology.sh
```

The four scripts perform different parts of the benchmark set:

1. `run_sysbench.sh`
   - Runs the sysbench CPU scaling test from 1 through 12 benchmark threads.
   - Each thread-count configuration is run five times.
   - Benchmark passes alternate between ascending and descending thread
     counts.

2. `run_sysbench_topology.sh`
   - Compares six benchmark threads spread across all six physical cores
     against six benchmark threads restricted to three physical cores using
     both hardware threads on each core.
   - Each configuration is run five times.

3. `run_7zip.sh`
   - Runs the 7-Zip built-in benchmark from 1 through 12 benchmark threads.
   - Each thread-count configuration is run five times.
   - Each benchmark run uses three internal 7-Zip iterations.
   - Benchmark passes alternate between ascending and descending thread
     counts.

4. `run_7zip_topology.sh`
   - Repeats the six-thread topology comparison using the 7-Zip benchmark.
   - Each configuration is run five times, with three internal 7-Zip
     iterations per run.

## 4. CPU-idle validation and retries

The scripts check CPU activity before and after every benchmark run using
`mpstat`.

All 12 logical CPUs are sampled for five seconds. A validation check passes
only when every logical CPU averages at least 94% idle over that interval.

If a pre-test idle check fails, the script waits and repeats the check rather
than immediately starting the benchmark.

If the benchmark completes but the post-test idle check fails, that
measurement is not marked as complete. The validation is retried according
to the script's retry logic.

This is intended to reduce the chance that a scheduled background process or
other temporary CPU activity becomes part of an accepted benchmark result.

### Resuming an interrupted or failed sequence

The benchmark scripts keep track of individual runs that have completed
successfully.

If a script is stopped, interrupted, or cannot complete an individual test
after its retry attempts, running the same script again does **not** restart
the entire benchmark sequence from the beginning.

Previously completed individual tests are skipped and the script resumes
from the first test that has not been successfully completed.

For example, if a sysbench sequence has successfully completed all runs up
to a particular thread-count/repetition combination and stops while
validating that run, rerunning:

```bash
bash scripts/run_sysbench.sh
```

will skip the already completed runs and continue from the incomplete one.

The same resume behaviour applies to the topology and 7-Zip scripts.

## 5. Raw benchmark output

The shell scripts write their benchmark and validation output under:

```text
data/raw/
```

The repository separates the four test groups into:

```text
data/raw/sysbench/
data/raw/sysbench-topology/
data/raw/7zip/
data/raw/7zip-topology/
```

The raw files are retained so that the processed results can be traced back
to the individual benchmark runs.

## 6. Generate the processed CSV files

After the benchmark runs have completed, generate the processed datasets
from the raw result files:

```bash
python3 analysis/parse_results.py
```

The parser reads the accepted benchmark result files and creates:

```text
data/processed/sysbench_scaling.csv
data/processed/sysbench_topology.csv
data/processed/7zip_scaling.csv
data/processed/7zip_topology.csv
```

The processed files retain the individual repetition measurements rather
than only the final averages. This makes it possible to verify the summary
statistics from the underlying runs.

By default, the parser also checks that the expected complete dataset is
present:

```text
sysbench scaling:    12 thread counts × 5 repetitions = 60 results
sysbench topology:    2 configurations × 5 repetitions = 10 results
7-Zip scaling:       12 thread counts × 5 repetitions = 60 results
7-Zip topology:       2 configurations × 5 repetitions = 10 results
```

If required while testing the parser against an incomplete dataset, the
completeness check can be bypassed with:

```bash
python3 analysis/parse_results.py --allow-partial
```

For the final published results, the complete dataset should be used.

## 7. Regenerate the figures

Once the CSV files have been generated, recreate the benchmark figures with:

```bash
python3 analysis/generate_figures.py
```

The figures are written to:

```text
figures/
```

The script calculates the plotted values from the processed CSV data rather
than using values entered manually.

## 8. Reproduction workflow

The complete workflow is therefore:

```text
scripts/run_sysbench.sh
scripts/run_sysbench_topology.sh
scripts/run_7zip.sh
scripts/run_7zip_topology.sh
        |
        v
data/raw/
        |
        v
analysis/parse_results.py
        |
        v
data/processed/*.csv
        |
        v
analysis/generate_figures.py
        |
        v
figures/*.png
```

The committed raw data represents the original benchmark runs used for the
article. The processed CSV files and figures can be regenerated from that
raw data without rerunning the benchmarks.
