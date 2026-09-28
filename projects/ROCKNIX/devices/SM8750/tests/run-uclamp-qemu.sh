#!/bin/sh
# Smoke-test the built SM8750 kernel and its embedded initramfs, without disks.
set -eu
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 /absolute/path/to/Image /absolute/path/to/test-output" >&2
    exit 2
fi
case "$1:$2" in /*:/*) ;; *) exit 2 ;; esac
test -f "$1"
command -v qemu-system-aarch64 >/dev/null
command -v cpio >/dev/null
package_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output=$2
mkdir -p "$output"
test_root=$(mktemp -d /tmp/odin3-uclamp-qemu.XXXXXX)
trap 'find "$test_root" -depth -delete' EXIT HUP INT TERM
install -m0755 "$package_dir/uclamp-qemu-init" "$test_root/cpu-smoke-init"
(cd "$test_root" && printf 'cpu-smoke-init\n' | cpio -o -H newc --owner=0:0) > "$test_root/overlay.cpio"
for layout in legacy unified; do
    timeout 120 qemu-system-aarch64 \
        -machine virt,gic-version=3 -cpu max -m 1024 -smp 2 \
        -nodefaults -no-reboot -display none -serial none -monitor none -nic none \
        -device virtio-serial-device -chardev stdio,id=console \
        -device virtconsole,chardev=console \
        -kernel "$1" -initrd "$test_root/overlay.cpio" \
        -append "console=hvc0 rdinit=/cpu-smoke-init panic=-1 clamp_test=$layout trace_test=${TRACE_SMOKE:-0}" \
        > "$output/$layout.log" 2>&1
    if grep -Fq 'UCLAMP-QEMU-FAIL' "$output/$layout.log"; then
        exit 1
    fi
    grep -Fq 'UCLAMP-QEMU-PASS' "$output/$layout.log"
    if [ "${TRACE_SMOKE:-0}" = 1 ]; then
        grep -Fq 'TRACE-QEMU-PASS' "$output/$layout.log"
    fi
    printf 'PASS: real kernel utilization clamps on %s controller\n' "$layout"
done
