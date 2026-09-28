# MangoApp frame logging

Patch `0004-mangoapp-explicit-ready-logging.patch` supports a nested compositor
that supplies application-ready intervals but no output intervals. Launch
Gamescope/MangoApp with `MANGOAPP_TIMING_SOURCE=app-ready` for that case. With
the variable unset, the receiver retains output timing. Unknown values also
retain output timing. The selection is fixed for the process lifetime; samples
never substitute one stream for the other or count both streams.

The patch reuses MangoApp's existing logging controls and duration limit. It
does not start logging automatically. Application-ready logs are named
`mangoapp-app-ready_*.csv`, including with the HUD hidden. Ready intervals are
not physical display presentation, and long intervals do not prove dropped
display frames. The sender must use the pinned MangoApp v1 field order:
`visible_frametime_ns` before `app_frametime_ns`.

The two SysV receivers own separate bounded buffers, including space for the
message type. Controls require a complete version-1/type-1 payload. Queue and
logger initialization precede both receiver threads. This is a targeted receiver
repair, not an audit of all upstream shared state.

## Validation

From the repository root, with the pinned MangoHud source tarball and a prepared
SM8750 MangoHud build/toolchain available:

```sh
python3 -B projects/ROCKNIX/packages/apps/mangohud/tools/test_frame_logging.py
```

The check applies the patch without fuzz, compiles and runs the actual timing
branch against synthetic ready/output/invalid samples, checks hidden-HUD
logging and receiver setup, then ARM64 syntax-checks both changed translation
units using the prepared build's compilation database. This is not a full
package link, live GPU test, or cross-device qualification.

This checkpoint contains the receiver repair, test and documentation only.
The nested Steam launcher integration remains separate pending review of its
other changes. No device image is installed by committing this patch, and
automatic randomized/headroom-gated logging is not implemented here.
