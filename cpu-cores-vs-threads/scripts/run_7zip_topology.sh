#!/usr/bin/env bash

# Public-release benchmark script for the article:
# "CPU Cores vs Threads: Theory, SMT, and Benchmark Performance"
#
# Compares two CPU topologies using the same six 7-Zip benchmark threads:
#
#   6 physical cores:
#     CPUs 0,1,2,3,4,5
#
#   3 physical cores using both SMT hardware threads:
#     CPUs 0,6,1,7,2,8
#
# Hardware topology used for the published results:
#   6 physical cores
#   2 hardware threads per core
#   12 logical CPUs
#   CPUs 0-5  = one hardware thread from each physical core
#   CPUs 6-11 = the second hardware thread from those same cores
#
# Each configuration is repeated five times, with test order alternated
# between passes to reduce systematic temperature/time-of-run bias.
#
# CPU idle is checked with mpstat before and after every benchmark run.
# A result is marked complete only after the benchmark and post-test
# validation both succeed.
#
# This script is expected to live in the article's scripts/ directory.
# Results are written beneath ../data/raw/.
#
# Requirements:
#   bash, 7z, taskset, mpstat

set -uo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_DIR" || exit 1

BASE="data/raw/7zip-topology"
COMPLETED="$BASE/completed"
INCOMPLETE="$BASE/incomplete"

mkdir -p "$BASE" "$COMPLETED" "$INCOMPLETE"

IDLE_THRESHOLD=94.0
MAX_RETRIES=5
RETRY_WAIT=15
RECOVERY_WAIT=10
EXPECTED_LOGICAL_CPUS=12

SEVENZIP_ITERATIONS=3
REPETITIONS=5

RUNSTAMP=$(date +%Y%m%d_%H%M%S)
MASTER="$BASE/7zip-topology-master-${RUNSTAMP}.txt"

exec > >(tee -a "$MASTER") 2>&1


require_command()
{
    local cmd="$1"

    if ! command -v "$cmd" >/dev/null 2>&1
    then
        echo "Required command not found: $cmd" >&2
        exit 1
    fi
}


check_cpu_idle()
{
    local prefix="$1"
    local phase="$2"

    local attempt=1
    local max_attempts=$((MAX_RETRIES + 1))

    while (( attempt <= max_attempts ))
    do
        local stamp
        stamp=$(date +%Y%m%d_%H%M%S)

        local outfile
        outfile="$BASE/${prefix}-${phase}-mpstat-attempt$(printf '%02d' "$attempt")-${stamp}.txt"

        echo
        echo "CPU idle check: $phase"
        echo "Attempt: ${attempt}/${max_attempts}"
        echo "Time: $(date --iso-8601=seconds)"

        if ! LC_ALL=C mpstat -P ALL 1 5 > "$outfile" 2>&1
        then
            echo "CPU check FAILED: mpstat command returned an error."
            echo "Saved: $outfile"
        elif awk -v threshold="$IDLE_THRESHOLD" -v expected="$EXPECTED_LOGICAL_CPUS" '
            /^Average:/ && $2 ~ /^[0-9]+$/ {
                count++
                if ($NF < threshold)
                    bad=1
            }
            END {
                if (count != expected || bad)
                    exit 1
            }
        ' "$outfile"
        then
            local min_idle
            min_idle=$(awk '
                /^Average:/ && $2 ~ /^[0-9]+$/ {
                    if (min == "" || $NF < min)
                        min=$NF
                }
                END {
                    print min
                }
            ' "$outfile")

            echo "CPU check PASSED."
            echo "Minimum logical CPU idle: ${min_idle}%"
            echo "Saved: $outfile"
            return 0
        else
            local min_idle
            local cpu_rows

            min_idle=$(awk '
                /^Average:/ && $2 ~ /^[0-9]+$/ {
                    if (min == "" || $NF < min)
                        min=$NF
                }
                END {
                    print min
                }
            ' "$outfile")

            cpu_rows=$(awk '
                /^Average:/ && $2 ~ /^[0-9]+$/ {
                    count++
                }
                END {
                    print count+0
                }
            ' "$outfile")

            echo "CPU check FAILED."
            echo "Logical CPU rows found: ${cpu_rows}/${EXPECTED_LOGICAL_CPUS}"
            if [[ -n "$min_idle" ]]
            then
                echo "Minimum logical CPU idle: ${min_idle}%"
            fi
            echo "Required minimum: ${IDLE_THRESHOLD}%"
            echo "Saved: $outfile"
        fi

        if (( attempt < max_attempts ))
        then
            echo "Waiting ${RETRY_WAIT} seconds before retry..."
            sleep "$RETRY_WAIT"
        fi

        attempt=$((attempt + 1))
    done

    echo
    echo "CPU remained unsuitable after ${max_attempts} checks."
    return 1
}


archive_incomplete_result()
{
    local result="$1"

    if [[ -f "$result" ]]
    then
        local stamp
        stamp=$(date +%Y%m%d_%H%M%S)

        local base
        base=$(basename "$result" .txt)

        local archived
        archived="$INCOMPLETE/${base}-${stamp}.txt"

        mv "$result" "$archived"

        echo "Previous unvalidated result archived:"
        echo "$archived"
    fi
}


run_test()
{
    local topology="$1"
    local cpus="$2"
    local pass="$3"

    local prefix
    prefix="7zip-topology-${topology}-r${pass}"

    local result="$BASE/${prefix}-result.txt"
    local done="$COMPLETED/${prefix}.done"

    echo
    echo "=================================================="
    echo "Topology: $topology"
    echo "7-Zip threads: 6"
    echo "CPU affinity: $cpus"
    echo "Pass: $pass"
    echo "=================================================="

    # Resume support.
    if [[ -f "$done" ]]
    then
        echo "Already completed - skipping."
        return 0
    fi

    # Preserve a result whose validation did not finish successfully.
    archive_incomplete_result "$result"

    # PRE-TEST CPU CHECK
    if ! check_cpu_idle "$prefix" "pre"
    then
        echo
        echo "Benchmark stopped before this test."
        echo "Topology: $topology"
        echo "Pass: $pass"
        echo
        echo "Run run_7zip_topology.sh later to resume here."
        exit 1
    fi

    # Write test metadata before appending the benchmark output.
    {
        echo "Timestamp: $(date --iso-8601=seconds)"
        echo "Benchmark: 7-Zip built-in benchmark"
        echo "Topology: $topology"
        echo "Threads: 6"
        echo "CPU affinity: $cpus"
        echo "7-Zip internal iterations: $SEVENZIP_ITERATIONS"
        echo
    } > "$result"

    # BENCHMARK
    if ! LC_ALL=C taskset -c "$cpus" \
        7z b "$SEVENZIP_ITERATIONS" -mmt=6 \
        >> "$result" 2>&1
    then
        echo
        echo "7-Zip benchmark command FAILED."
        archive_incomplete_result "$result"
        echo "Run the script later to retry this same configuration."
        exit 1
    fi

    echo "Benchmark completed: $result"

    # RECOVERY PERIOD
    sleep "$RECOVERY_WAIT"

    # POST-TEST CPU CHECK
    if ! check_cpu_idle "$prefix" "post"
    then
        echo
        echo "Post-test CPU validation failed."
        echo "This run will NOT be marked complete."
        echo
        echo "Run the script again later."
        echo "The same topology/pass will be rerun."
        exit 1
    fi

    # Mark valid only after successful post-test validation.
    {
        echo "Completed: $(date --iso-8601=seconds)"
        echo "Topology: $topology"
        echo "Threads: 6"
        echo "CPU affinity: $cpus"
        echo "Pass: $pass"
        echo "Iterations: $SEVENZIP_ITERATIONS"
        echo "Result: $result"
    } > "$done"

    echo "Run validated and marked complete."
}


require_command 7z
require_command taskset
require_command mpstat


echo "=================================================="
echo "7-ZIP CPU TOPOLOGY COMPARISON"
echo "Started: $(date --iso-8601=seconds)"
echo "Kernel: $(uname -r)"
echo
echo "6 physical cores:"
echo "  CPUs 0,1,2,3,4,5"
echo
echo "3 physical cores + SMT:"
echo "  CPUs 0,6,1,7,2,8"
echo
echo "Threads per benchmark: 6"
echo "7-Zip internal iterations: ${SEVENZIP_ITERATIONS}"
echo "Independent repetitions: ${REPETITIONS}"
echo "Idle threshold: ${IDLE_THRESHOLD}%"
echo "Idle-check retries: ${MAX_RETRIES}"
echo "=================================================="

echo
7z | head -n 5
echo


for pass in $(seq 1 "$REPETITIONS")
do
    echo
    echo "##################################################"
    echo "PASS $pass"
    echo "##################################################"

    # Alternate test order between passes.
    if (( pass % 2 == 1 ))
    then
        run_test "6physical" "0,1,2,3,4,5" "$pass"
        run_test "3physical-smt" "0,6,1,7,2,8" "$pass"
    else
        run_test "3physical-smt" "0,6,1,7,2,8" "$pass"
        run_test "6physical" "0,1,2,3,4,5" "$pass"
    fi
done


echo
echo "=================================================="
echo "ALL 7-ZIP TOPOLOGY RUNS COMPLETED"
echo "Completed: $(date --iso-8601=seconds)"
echo "=================================================="
