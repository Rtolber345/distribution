"""Compile the shipped focus guard, and exercise the real Steam launcher with mocks."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[4]
SOURCE = REPO / 'sources/gamescope/gamescope-428688779e481681ddf6e2ea346987889527a0b7/src/steamcompmgr.cpp'
PATCH = PACKAGE / 'patches/0010-steam-silent-launch-focus-fallback.patch'
LAUNCHER = PACKAGE.parents[1] / 'emulators/standalone/steam/scripts/start_steam.sh'


class SteamFocusTests(unittest.TestCase):
    def test_native_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            shutil.copyfile(SOURCE, root / 'src/steamcompmgr.cpp')
            subprocess.run(['patch', '--fuzz=0', '-p1', '-i', str(PATCH)], cwd=root, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            source = (root / 'src/steamcompmgr.cpp').read_text()
            begin = source.index('\t// Keep the fallback local:')
            end = source.index('\n\tgameFocused = pick_primary_focus_and_override(', begin)
            guard = source[begin:end]
            self.assertIn('true, focusControlAppIDs,', source[end:end + 220])
            self.assertNotIn('XChangeProperty', guard)
            harness = r'''
#include <cassert>
#include <cstdint>
#include <vector>
constexpr unsigned long None = 0;
namespace gamescope {
namespace VirtualConnectorStrategies { constexpr int SteamControlled = 1; }
int cv_backend_virtual_connector_strategy = 1;
}
struct steamcompmgr_win_t {
    uint32_t appID;
    bool useless = false, skip = false, redirect = false, disabled = false, commits = true;
};
bool win_is_useless(steamcompmgr_win_t *w) { return w->useless; }
bool win_skip_and_not_fullscreen(steamcompmgr_win_t *w) { return w->skip; }
bool win_is_override_redirect(steamcompmgr_win_t *w) { return w->redirect; }
bool win_is_disabled(steamcompmgr_win_t *w) { return w->disabled; }
bool window_has_commits(steamcompmgr_win_t *w) { return w->commits; }
struct Focus {
    steamcompmgr_win_t *focusWindow = nullptr;
    bool nested = true;
    bool GetNestedHints() { return nested; }
};
struct Root { unsigned long focusControlWindow = None; };
struct Log { void infof(const char *, uint32_t) {} } focus_log;
std::vector<uint32_t> select(uint32_t cv_orbital_steam_fallback_appid, Focus *pFocus, Root *root_ctx,
    const std::vector<steamcompmgr_win_t *> &vecPossibleFocusWindows,
    const std::vector<uint32_t> &vecFocuscontrolAppIDs = {}) {
''' + guard + r'''
    return focusControlAppIDs;
}
int main() {
    steamcompmgr_win_t requested{2552430}, other{1234};
    Focus focus;
    Root root;
    std::vector<steamcompmgr_win_t *> windows{&other, &requested};
    const std::vector<uint32_t> expected{2552430};
    auto pick = [&] { return select(2552430, &focus, &root, windows); };
    assert(pick() == expected);
    assert(select(0, &focus, &root, windows).empty());
    assert(select(9876, &focus, &root, windows).empty());
    assert(select(2552430, &focus, &root, {}).empty());
    assert(select(2552430, &focus, &root, windows, {1234}) == std::vector<uint32_t>{1234});
    assert(select(2552430, &focus, &root, windows, {0}) == std::vector<uint32_t>{0});
    root.focusControlWindow = 9;
    assert(pick().empty());
    root.focusControlWindow = None;
    focus.focusWindow = &other;
    assert(pick().empty());
    focus.focusWindow = &requested;
    assert(pick() == expected); // retain normal dialog/window selection on later rerolls
    focus.focusWindow = nullptr;
    for (auto member : {&steamcompmgr_win_t::useless, &steamcompmgr_win_t::skip,
                       &steamcompmgr_win_t::redirect, &steamcompmgr_win_t::disabled}) {
        requested.*member = true;
        assert(pick().empty());
        requested.*member = false;
    }
    requested.commits = false;
    assert(pick().empty());
    requested.commits = true;
    focus.nested = false;
    assert(pick().empty());
    focus.nested = true;
    gamescope::cv_backend_virtual_connector_strategy = 2;
    assert(pick().empty());
    gamescope::cv_backend_virtual_connector_strategy = 1;
    windows.clear(); // game closed; no stale selection is published
    assert(pick().empty());
}
'''
            binary = root / 'test-focus'
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-x', 'c++',
                            '-o', str(binary), '-'], input=harness, text=True, check=True)
            subprocess.run([str(binary)], check=True, timeout=5)

    def test_launcher_opt_in_and_validation(self):
        script = r'''
source "$1"
mkdir() { :; }; touch() { :; }; gamescope() { :; }; FEX() { :; }
systemctl() { :; }; steam_input_target_begin() { :; }; steam_session_cleanup() { :; }
env() { printf '<%s>\n' "$@"; }
ROCKNIX_STEAM_NESTED=$3 STEAM_FLAVOR=$4 LOGICAL_W=1920 LOGICAL_H=1080
steam_launch_bigpicture "$2" steam
'''
        with tempfile.TemporaryDirectory() as directory:
            desktop = Path(directory) / 'Game.desktop'
            for nested, flavor, command, expected in [
                ('1', 'arm64', 'steam steam://rungameid/2552430', '2552430'),
                ('1', 'arm64', 'steam steam://rungameid/4294967295', '4294967295'),
                ('0', 'arm64', 'steam steam://rungameid/2552430', '0'),
                ('1', 'arm64', 'steam steam://rungameid/0', '0'),
                ('1', 'arm64', 'steam steam://rungameid/01', '0'),
                ('1', 'arm64', 'steam steam://rungameid/4294967296', '0'),
                ('1', 'arm64', 'steam steam://rungameid/123; false', '0'),
                ('1', 'arm64', 'steam steam://rungameid/$(false)', '0'),
                ('1', 'arm64', 'steam steam://rungameid/-1', '0'),
                ('1', 'x86', 'steam steam://rungameid/2552430', None),
            ]:
                with self.subTest(nested=nested, flavor=flavor, command=command):
                    desktop.write_text('[Desktop Entry]\nExec=' + command + '\n')
                    result = subprocess.run(['bash', '-c', script, 'test', str(LAUNCHER),
                                             str(desktop), nested, flavor], check=True,
                                            capture_output=True, text=True, timeout=5)
                    if expected is None:
                        self.assertNotIn('gamescope_orbital_steam_fallback_appid=', result.stdout)
                    else:
                        self.assertIn('<gamescope_orbital_steam_fallback_appid=' + expected + '>', result.stdout)
                        timing = 'app-ready' if nested == '1' else 'output'
                        self.assertIn('<MANGOAPP_TIMING_SOURCE=' + timing + '>', result.stdout)
                    self.assertIn('<steam://rungameid/', result.stdout)
            desktop = Path(directory) / 'Steam.desktop'
            desktop.write_text('[Desktop Entry]\nExec=steam\n')
            result = subprocess.run(['bash', '-c', script, 'test', str(LAUNCHER), str(desktop), '1', 'arm64'],
                                    check=True, capture_output=True, text=True, timeout=5)
            self.assertIn('<gamescope_orbital_steam_fallback_appid=0>', result.stdout)
            self.assertIn('<-gamepadui>', result.stdout)


if __name__ == '__main__':
    unittest.main()
