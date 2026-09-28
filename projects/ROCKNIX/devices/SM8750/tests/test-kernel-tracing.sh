#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
set -eu

test_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
config="${1:-${test_dir}/../linux/linux.aarch64.conf}"

for option in FTRACE TRACING TRACEPOINTS EVENT_TRACING FUNCTION_TRACER \
    FUNCTION_GRAPH_TRACER DYNAMIC_FTRACE FTRACE_SYSCALLS KPROBES KPROBE_EVENTS \
    UPROBE_EVENTS TRACER_SNAPSHOT BPF_UNPRIV_DEFAULT_OFF; do
    if [ "$(grep -c "^CONFIG_${option}=y$" "$config" || true)" != 1 ]; then
        printf 'Missing tracing prerequisite: CONFIG_%s=y\n' "$option" >&2
        exit 1
    fi
done

grep -qx 'CONFIG_TRACE_SYSCALL_BUF_SIZE_DEFAULT=0' "$config"

for option in BOOTTIME_TRACING FUNCTION_PROFILER STACK_TRACER IRQSOFF_TRACER \
    PREEMPT_TRACER SCHED_TRACER HWLAT_TRACER OSNOISE_TRACER FTRACE_STARTUP_TEST \
    EVENT_TRACE_STARTUP_TEST; do
    if grep -q "^CONFIG_${option}=[ym]$" "$config"; then
        printf 'Unexpected extra tracer: CONFIG_%s\n' "$option" >&2
        exit 1
    fi
done

printf 'SM8750 opt-in kernel tracing configuration passed: %s\n' "$config"
