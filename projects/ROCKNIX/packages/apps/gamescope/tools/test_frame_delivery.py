import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("report", ROOT / "tools/frame-delivery-report.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class DeliveryTests(unittest.TestCase):
    def test_correlation_clock_domains_discards_and_reused_feedback_id(self):
        markers = [
            "stage=ready commit=5 mono_ns=1000000 desired_ns=0",
            "stage=submit feedback=8 base_commit=5 mono_ns=2000000",
            "stage=presented feedback=8 host_ns=4000000 host_clock=1 refresh_ns=8333333",
            "stage=submit feedback=8 base_commit=6 mono_ns=5000000",
            "stage=discarded feedback=8",
            "stage=presented feedback=999 host_ns=9000000 host_clock=0",
        ]
        result = report.analyze(f"gamescope-{100 + index} [002] 1.00: tracing_mark_write: orbital_frame pid=12 " + marker
                                for index, marker in enumerate(markers))["processes"][12]
        self.assertEqual(result["ready_to_host_ms"]["median_ms"], 3)
        self.assertEqual(result["submit_to_host_ms"]["median_ms"], 2)
        self.assertEqual(result["host_surface_interval_ms"]["count"], 0)
        self.assertEqual(result["discarded"], 1)
        self.assertEqual(result["unpaired"], 1)

    def test_malformed_and_empty_trace(self):
        self.assertEqual(report.analyze(["unrelated log\n"])["events"], 0)
        self.assertEqual(report.analyze(["gamescope-12 [2] orbital_frame stage=ready commit=no"])["events"], 0)

    def test_patch_targets_real_wayland_callbacks_and_corrects_wire_order(self):
        patch = (ROOT / "patches/0009-frame-delivery-trace-and-mangoapp-abi.patch").read_text()
        self.assertIn("Wayland_PresentationFeedback_Discarded", patch)
        self.assertIn("host_clock=%u", patch)
        self.assertIn("base_commit=%llu", patch)
        self.assertLess(patch.index("+    uint64_t visible_frametime_ns;"),
                        patch.index("+    uint64_t app_frametime_ns;"))


if __name__ == "__main__":
    unittest.main()
