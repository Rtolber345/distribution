"""Apply the project patch to disposable copies of the pinned build inputs."""
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
BUILD = PACKAGE.parents[4] / "build.ROCKNIX-SM8750.aarch64/build"
GAMESCOPE = BUILD / "gamescope-428688779e481681ddf6e2ea346987889527a0b7"
UPSTREAM = PACKAGE.parents[4] / "sources/gamescope" / GAMESCOPE.name
MANGO = BUILD / "mangohud-992103e4fb744897826de04ea00a2f71e7018214"


@unittest.skipUnless(GAMESCOPE.is_dir() and MANGO.is_dir(), "pinned sources not present")
class PinnedBuildTests(unittest.TestCase):
    def test_patch_wire_abi_and_cross_compile(self):
        with tempfile.TemporaryDirectory(prefix="orbital-frame-build-") as directory:
            root = Path(directory)
            names = ("src/commit.cpp", "src/mangoapp.cpp", "src/Backends/WaylandBackend.cpp")
            for name in names:
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(UPSTREAM / name, destination)
            result = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i",
                str(PACKAGE / "patches/0009-frame-delivery-trace-and-mangoapp-abi.patch")],
                cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            definitions = []
            for path in (root / "src/mangoapp.cpp", MANGO / "src/app/mangoapp_proto.h"):
                text = path.read_text()
                header = re.search(r"struct mangoapp_msg_header \{.*?\} __attribute__\(\(packed\)\);", text, re.S)[0]
                payload = re.search(r"struct mangoapp_msg_v1 \{.*?\} __attribute__\(\(packed\)\)", text, re.S)[0]
                definitions.append(header + "\n" + payload + ";")
            abi = root / "abi.cpp"
            abi.write_text("#include <stdint.h>\n#include <stddef.h>\nnamespace sender {" + definitions[0]
                + "}\nnamespace receiver {" + definitions[1] + "}\n" + "\n".join(
                f"static_assert(offsetof(sender::mangoapp_msg_v1, {field}) == offsetof(receiver::mangoapp_msg_v1, {field}));"
                for field in ("pid", "visible_frametime_ns", "app_frametime_ns", "latency_ns", "outputWidth", "outputHeight")))
            subprocess.run(["c++", "-std=c++20", "-Werror", "-fsyntax-only", str(abi)], check=True)
            compile_dir = GAMESCOPE / ".aarch64-rocknix-linux-gnu"
            commands = json.loads((compile_dir / "compile_commands.json").read_text())
            compiled = []
            for entry in commands:
                relative = entry["file"].removeprefix("../")
                if relative not in names:
                    continue
                args = shlex.split(entry["command"])
                filtered = []
                skip = False
                for argument in args:
                    if skip:
                        skip = False
                    elif argument in ("-o", "-MF", "-MQ", "-MT"):
                        skip = True
                    elif argument not in ("-c", "-MD", "-MMD", entry["file"]):
                        filtered.append(argument)
                filtered += ["-fsyntax-only", str(root / relative)]
                result = subprocess.run(filtered, cwd=compile_dir, capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                compiled.append(relative)
            self.assertEqual(set(compiled), set(names))


if __name__ == "__main__":
    unittest.main()
