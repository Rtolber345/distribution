#!/usr/bin/env python3
"""Summarize opt-in Orbital GPUVis markers, without calling frame intervals drops."""
import argparse
from collections import OrderedDict
import json
import os
import re
import stat
import statistics

MAX_BYTES = 64 * 1024 * 1024
MAX_EVENTS = 200000
LINE = re.compile(r"-(\d+)\s+(?:\(\s*\d+\)\s+)?\[\d+\].*?orbital_frame (.*)")


def summary(values):
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {"count": len(values), "median_ms": round(statistics.median(values), 3),
            "p95_ms": round(ordered[int((len(values) - 1) * .95)], 3),
            "p99_ms": round(ordered[int((len(values) - 1) * .99)], 3),
            "max_ms": round(max(values), 3)}


def analyze(lines):
    ready, pending = OrderedDict(), OrderedDict()
    reports = {}
    total = events = 0
    for line in lines:
        total += len(line.encode("utf-8"))
        if total > MAX_BYTES or events >= MAX_EVENTS:
            raise ValueError("trace exceeds the analysis budget")
        match = LINE.search(line)
        if not match:
            continue
        fields = dict(item.split("=", 1) for item in match[2].split() if "=" in item)
        stage = fields.pop("stage", "")
        try:
            fields = {key: int(value) for key, value in fields.items()}
        except ValueError:
            continue
        if any(not 0 <= value < 2**64 for value in fields.values()):
            continue
        # ftrace's prefix contains a thread ID, not a process ID. Ready and
        # presentation callbacks run on different Gamescope threads.
        pid = fields.pop("pid", 0)
        if pid <= 0:
            continue
        events += 1
        if pid not in reports:
            if len(reports) >= 64:
                raise ValueError("too many traced processes")
            reports[pid] = dict(presented=0, discarded=0, unpaired=0,
                ready_to_host_ms=[], submit_to_host_ms=[], host_surface_interval_ms=[],
                new_base_interval_ms=[], last_host=None, last_base=None, last_base_time=None)
        result = reports[pid]
        if stage == "ready" and {"commit", "mono_ns"} <= fields.keys():
            ready[(pid, fields["commit"])] = fields["mono_ns"]
        elif stage == "submit" and {"feedback", "base_commit", "mono_ns"} <= fields.keys():
            pending[(pid, fields["feedback"])] = fields
        elif stage in ("presented", "discarded") and "feedback" in fields:
            submit = pending.pop((pid, fields["feedback"]), None)
            result[stage] += 1
            if submit is None:
                result["unpaired"] += 1
            if stage == "presented" and {"host_ns", "host_clock"} <= fields.keys():
                host = fields["host_ns"]
                previous = result["last_host"]
                if previous and previous[0] == fields["host_clock"] and host > previous[1]:
                    result["host_surface_interval_ms"].append((host - previous[1]) / 1e6)
                result["last_host"] = (fields["host_clock"], host)
                # CLOCK_MONOTONIC=1 on Linux. Never subtract unrelated clocks.
                if submit and fields["host_clock"] == 1:
                    if host >= submit["mono_ns"]:
                        result["submit_to_host_ms"].append((host - submit["mono_ns"]) / 1e6)
                    base = submit["base_commit"]
                    if base != result["last_base"]:
                        stamp = ready.get((pid, base))
                        if stamp is not None and host >= stamp:
                            result["ready_to_host_ms"].append((host - stamp) / 1e6)
                        last = result["last_base_time"]
                        if last is not None and host > last:
                            result["new_base_interval_ms"].append((host - last) / 1e6)
                        result["last_base"], result["last_base_time"] = base, host
        for cache in (ready, pending):
            while len(cache) > 16384:
                cache.popitem(last=False)
    output = {}
    for pid, result in reports.items():
        output[pid] = {key: summary(value) if isinstance(value, list) else value
                       for key, value in result.items() if not key.startswith("last_")}
    return {"schema": "io.orbital.frame-delivery-report.v1", "events": events,
            "processes": output,
            "note": "Host surface feedback, not proof of physical panel delivery or game frame loss."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace")
    args = parser.parse_args()
    fd = os.open(args.trace, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
        os.close(fd)
        parser.error("trace must be a regular file no larger than 64 MiB")
    with os.fdopen(fd, encoding="utf-8", errors="replace") as stream:
        print(json.dumps(analyze(stream), indent=2))
