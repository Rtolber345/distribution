"""Exercise the patched timing branch and syntax-check actual ARM64 inputs."""
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[4]
NAME = 'mangohud-992103e4fb744897826de04ea00a2f71e7018214'
UPSTREAM = 'MangoHud-992103e4fb744897826de04ea00a2f71e7018214'
BUILD = REPO / 'build.ROCKNIX-SM8750.aarch64/build' / NAME


class FrameLoggingTests(unittest.TestCase):
    def test_patched_receiver_and_target_compilation(self):
        with tempfile.TemporaryDirectory(prefix='mango-log-test-') as directory:
            root = Path(directory)
            with tarfile.open(REPO / 'sources/mangohud' / (NAME + '.tar.gz')) as archive:
                for name in ('src/app/main.cpp', 'src/app/mangoapp_proto.h', 'src/logging.cpp'):
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.extractfile(UPSTREAM + '/' + name).read())
            subprocess.run(['patch', '--fuzz=0', '-p1', '-i', str(PACKAGE /
                'patches/common/0004-mangoapp-explicit-ready-logging.patch')], cwd=root, check=True)
            source = (root / 'src/app/main.cpp').read_text()
            self.assertNotIn('static uint8_t raw_msg', source)
            self.assertEqual(source.count('uint8_t raw_msg[1024 + sizeof(long)]'), 2)
            self.assertIn('mangoapp_ctrl_v1->hdr.ctrl_msg_type != 1', source)
            self.assertIn('mangoapp_ctrl_v1->hdr.version != 1', source)
            self.assertIn('msg_size < sizeof(mangoapp_msg_v1) - sizeof(long)', source)
            self.assertLess(source.index('msgid = msgget('), source.index('std::thread(msg_read_thread)'))
            self.assertLess(source.index('logger = std::make_unique'), source.index('std::thread(msg_read_thread)'))
            begin = source.index('                    const uint64_t frametime_ns =')
            end = source.index('\n\n                    if (msg_size', begin)
            branch = source[begin:end]
            harness = r'''
#include <cassert>
#include <cstdint>
#include <vector>
#include "src/app/mangoapp_proto.h"
std::vector<uint64_t> samples;
int sw_stats = 0, params = 0, vendorID = 0;
struct Params { bool no_display = true; } settings;
struct Log { bool active = true; bool is_active() { return active; } } log_state;
auto logger = &log_state;
void update_hud_info_with_frametime(int, int, int, uint64_t ns) { samples.push_back(ns); }
bool receive(bool app_ready, const mangoapp_msg_v1 *mangoapp_v1) {
    auto real_params = &settings;
    bool should_new_frame = false;
''' + branch + r'''
    return should_new_frame;
}
int main() {
    mangoapp_msg_v1 ready{}, output{};
    ready.visible_frametime_ns = uint64_t(-1);
    ready.app_frametime_ns = 16666667;
    output.visible_frametime_ns = 33333333;
    output.app_frametime_ns = uint64_t(-1);
    assert(receive(true, &ready));
    assert(!receive(true, &output));
    assert(!receive(false, &ready));
    assert(receive(false, &output));
    assert(samples.size() == 2);
    assert(samples[0] == 16666667 && samples[1] == 33333333);
    log_state.active = false;
    assert(!receive(true, &ready));
    settings.no_display = false;
    assert(receive(true, &ready));
    ready.app_frametime_ns = 0;
    assert(!receive(true, &ready));
    ready.app_frametime_ns = uint64_t(-1);
    assert(!receive(true, &ready));
}
'''
            fixture = root / 'test.cpp'
            fixture.write_text(harness)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            str(fixture), '-o', str(root / 'test')], check=True)
            subprocess.run([str(root / 'test')], check=True)
            logging = (root / 'src/logging.cpp').read_text()
            self.assertIn('program += "-app-ready"', logging)
            self.assertIn('program == "mangoapp"', logging)
            compile_dir = BUILD / '.aarch64-rocknix-linux-gnu'
            commands = json.loads((compile_dir / 'compile_commands.json').read_text())
            pending = {'src/app/main.cpp', 'src/logging.cpp'}
            for entry in commands:
                name = entry['file'].removeprefix('../')
                if name not in pending:
                    continue
                args, skip = [], False
                for arg in shlex.split(entry['command']):
                    if skip:
                        skip = False
                    elif arg in ('-o', '-MF', '-MQ', '-MT'):
                        skip = True
                    elif arg not in ('-c', '-MD', '-MMD', entry['file']):
                        args.append(arg)
                args += ['-I' + str((BUILD / name).parent), '-fsyntax-only', str(root / name)]
                subprocess.run(args, cwd=compile_dir, check=True, timeout=120)
                pending.remove(name)
            self.assertFalse(pending)


if __name__ == '__main__':
    unittest.main()
