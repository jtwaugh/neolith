import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from pipeline.lock import build_lock


class Lock(unittest.TestCase):
    def test_second_holder_waits(self):
        with tempfile.TemporaryDirectory() as d:
            order = []

            def second():
                with build_lock(d, log=lambda m: order.append("waiting"), poll=0.05):
                    order.append("second")
            with build_lock(d):
                t = threading.Thread(target=second)
                # flock is per open file, so a thread with its own open() contends.
                os.environ.pop("PIPELINE_LOCK_HELD", None)
                t.start()
                time.sleep(0.3)
                order.append("first done")
            t.join(5)
            self.assertEqual(order, ["waiting", "first done", "second"])

    def test_child_under_held_lock_does_not_wait(self):
        with tempfile.TemporaryDirectory() as d:
            code = ("from pipeline.lock import build_lock\n"
                    f"with build_lock({d!r}, timeout=2): print('ok')")
            r = subprocess.run([sys.executable, "-m", "pipeline.lock", d, "--", sys.executable, "-c", code],
                               capture_output=True, text=True, timeout=20)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
