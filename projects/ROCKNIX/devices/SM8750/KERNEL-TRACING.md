# Opt-in kernel diagnostics

SM8750 enables tracefs events, dynamic function/function-graph tracing, syscall
events, kprobes, uprobes and snapshots. This exposes existing qcom_glink,
scheduler, IRQ, workqueue and available GPU/fence tracepoints, plus Gamescope's
opt-in GPUVis markers. No logging daemon or automatic capture is added.

Default operation uses the nop tracer, no enabled events and no probes. Do not
enable all-function tracing, startup self-tests or high-frequency continuous
capture on a gaming console. Compiled support is not zero overhead; measure
idle/game performance after the new kernel is installed.

Capture only through an authorized administrator/developer path. Keep tracefs
root-owned and restricted; do not chmod its controls for applications or weaken
SELinux. Check the running kernel's available events rather than assuming every
event exists. Syscall user-buffer recording defaults to zero bytes; do not
enable payload capture for this investigation. Start with a 20-second,
1024-KiB-per-CPU RAM ring and narrowly
selected qcom_glink events; add scheduler/fence events for a separate frame
delivery investigation. On an eight-CPU device that is approximately 8 MiB
plus metadata (and another ring if a snapshot is allocated).

Never overwrite another tracing session. Stop and disable the events/probes
and restore the nop tracer when finished: tracing_on=0 alone does not remove
instrumentation overhead. Save the bounded result privately; traces can expose
process names, paths and addresses. Record overwritten/lost events and clock
selection. Do not count ready-time gaps as proven missed panel presentations.

Capture to RAM independently of journald: power-supply uevent metadata reads
can block journald itself during a GLINK fault. Copy evidence off-device before
reboot. This ring is volatile; existing pstore support does not guarantee trace
persistence, and no reserved-memory or recovery-partition change is made here.

Run `sh projects/ROCKNIX/devices/SM8750/tests/test-kernel-tracing.sh` from the
repository root. Pass a resolved kernel .config as its optional argument to
check Kconfig dependency resolution too. This checks capability selection, not
runtime capture. Rebuild and qualify the kernel plus its matching modules;
do not replace only KERNEL while retaining incompatible modules.

For a diskless virtual-machine smoke test of the built kernel and embedded
initramfs, run `TRACE_SMOKE=1 tests/run-uclamp-qemu.sh /absolute/path/to/Image
/absolute/path/to/results` from this device directory. It checks tracing starts
idle, records a bounded scheduler event, disables it, and exercises both cgroup
layouts. This verifies real kernel behavior, not the Odin DSP or GPU hardware.

References: [ftrace](https://docs.kernel.org/trace/ftrace.html),
[kprobe events](https://docs.kernel.org/trace/kprobetrace.html),
[uprobe events](https://docs.kernel.org/trace/uprobetracer.html).
