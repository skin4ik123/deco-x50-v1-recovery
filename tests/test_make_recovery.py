# SPDX-License-Identifier: GPL-2.0-or-later
"""Fail-closed checks plus optional integration with the genuine firmware.

Set DECO_STOCK_BIN to the genuine extracted BIN for the full suite.
No firmware is committed to the repository or flashed by these tests.
"""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "make_recovery", Path(__file__).resolve().parents[1] / "tools" / "make_recovery.py"
)
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


class FailClosedTests(unittest.TestCase):
    def test_unrelated_and_truncated_files_are_rejected(self):
        for data in (b"", b"UBI#" + bytes(100), b"unrelated firmware"):
            with self.subTest(size=len(data)), self.assertRaises(recovery.RecoveryError):
                recovery.make_candidate(data)

    def test_existing_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "existing.bin"
            target.write_bytes(b"keep this")
            with self.assertRaises(FileExistsError):
                recovery.save_new(target, b"replacement")
            self.assertEqual(target.read_bytes(), b"keep this")

    def test_symlink_is_never_followed_for_output(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target.bin"
            target.write_bytes(b"keep this")
            link = Path(folder) / "link.bin"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("This platform does not permit creating symlinks")
            with self.assertRaises(FileExistsError):
                recovery.save_new(link, b"replacement")
            self.assertEqual(target.read_bytes(), b"keep this")

    def test_cli_does_not_create_output_for_wrong_firmware(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "wrong.bin"
            source.write_bytes(b"not a supported firmware")
            target = Path(folder) / "output.bin"
            self.assertEqual(recovery.main(["--input", str(source), "--output", str(target)]), 1)
            self.assertFalse(target.exists())


@unittest.skipUnless(os.environ.get("DECO_STOCK_BIN"), "Set DECO_STOCK_BIN for genuine-image integration")
class GenuineImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(os.environ["DECO_STOCK_BIN"])
        cls.source = recovery.read_source(cls.path)

    def test_reference_and_only_three_changed_bytes(self):
        candidate = recovery.make_candidate(self.source)
        self.assertEqual(len(candidate), recovery.SOURCE_BYTES)
        self.assertEqual(recovery.sha256(candidate), recovery.CANDIDATE_SHA256)
        changed = [i for i, (a, b) in enumerate(zip(self.source, candidate)) if a != b]
        self.assertEqual(changed, [1, 2, 3])
        self.assertEqual(recovery.sha256(self.path.read_bytes()), recovery.SOURCE_SHA256)

    def test_one_payload_bit_is_rejected(self):
        altered = bytearray(self.source)
        altered[0x2814] ^= 1
        with self.assertRaises(recovery.RecoveryError):
            recovery.make_candidate(altered)

    def test_already_patched_input_is_rejected(self):
        with self.assertRaises(recovery.RecoveryError):
            recovery.make_candidate(recovery.make_candidate(self.source))

    def test_cli_round_trip_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "candidate.bin"
            self.assertEqual(recovery.main(["--input", str(self.path), "--output", str(target)]), 0)
            self.assertEqual(recovery.main(["--check", str(target)]), 0)
            with target.open("r+b") as stream:
                stream.seek(0x2814)
                stream.write(bytes([self.source[0x2814] ^ 1]))
            self.assertEqual(recovery.main(["--check", str(target)]), 1)


if __name__ == "__main__":
    unittest.main()
