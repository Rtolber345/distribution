# Frame-delivery diagnostics

Source implementation, not a deployed performance fix. Patch 0009 adds opt-in
GPUVis markers to the actual Wayland backend and commit fence-ready path. It
also corrects the pinned Gamescope/MangoApp v1 field order (visible timing first,
application timing second). Deploy the rebuilt Gamescope with the pinned
MangoApp; don't reinterpret previous CSVs as scanout measurements.

Set `gamescope_orbital_frame_trace=1` for a diagnostic game launch. Default is
off. These markers use the existing GPUVis trace-marker path, not journald,
files in the render loop, a new daemon, or another CPU scheduler. Root/developer
tracing permission is required; do not loosen tracefs permissions for games.
Use the existing GPUVis/ftrace capture tooling with a finite capture window
(start with 20 seconds), a fixed ring-buffer budget (1024 KiB per CPU), and stop
tracing afterwards. Do not reconfigure another active tracing session. Preserve
the captured ring in a private diagnostic file; it can contain other process
names. The report emits only the new numeric markers.

Markers: `ready(commit, mono_ns, desired_ns)`,
`submit(feedback, base_commit, mono_ns)`,
`presented(feedback, host_ns, host_clock, refresh_ns, sequence, flags,
callback_mono_ns)`, and `discarded(feedback, callback_mono_ns)`.
Every marker includes the process ID (the trace prefix is only a thread ID).
IDs are process-local and feedback IDs can be reused after completion. The
base commit is the selected game content; the host surface may also contain
overlays/repaints. A surface discard is not necessarily a lost game frame.
The report subtracts host and ready clocks only for Linux CLOCK_MONOTONIC.
Missing/overwritten trace events stay unpaired, never guessed.

Run `python3 tools/frame-delivery-report.py CAPTURE` from this package.
Input is capped at 64 MiB/200,000 markers/64 processes; join caches are bounded.
Compare ready-to-host and submit-to-host tails and new-base cadence across
repeated identical scenes. Correlate a short scheduler/fence trace if needed.
This does not diagnose striped video decoding, fix firmware transport, or prove
physical panel scanout. No limiter, clock, or scheduling policy is changed here.

## Nested MangoApp logging

The nested Steam launcher selects `MANGOAPP_TIMING_SOURCE=app-ready`; standalone
DRM retains `output`. MangoApp patch 0004 selects exactly one field for a session
and names application-ready CSVs `mangoapp-app-ready_*.csv`. It never substitutes
one timing source for another per packet (which would double-count frames when
both streams exist). Control/frame receivers have separate bounded buffers.
Existing explicit start/stop and log-duration settings are reused; logging is
not enabled by default. Hidden-HUD logging can update from the selected stream.

Do not label application-ready FPS as physical panel presentation or count long
intervals as confirmed dropped frames. The current Odin kernel has FTRACE
disabled; patch 0009 alone does not make the GPUVis capture available. A future
kernel must enable and validate the necessary tracing before launch. The
2026-09-28 live workaround used a bounded private RAM capture of the existing
MangoApp feed, temporarily pausing only the statistics helper with a pidfd
watchdog that resumes it. No game/compositor restart or instrumentation injection.
