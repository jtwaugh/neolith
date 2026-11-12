"""One pipeline run at a time per build directory.

Commands that write into the build directory take an exclusive lock on
<build_dir>/.lock for their whole run, so two sessions can't interleave
writes to report.md, combined_map.geojson or settlements.geojson. A second
run waits for the first, saying who holds the lock.

`python -m pipeline.lock BUILD_DIR -- CMD ...` runs a whole recipe (the
pipeline, then the converter) under the lock; pipeline runs inside it see
PIPELINE_LOCK_HELD and don't wait on themselves.
"""
import contextlib
import fcntl
import os
import time


@contextlib.contextmanager
def build_lock(build_dir, log=lambda m: print(m, flush=True), poll=5.0, timeout=None):
    os.makedirs(build_dir, exist_ok=True)
    path = os.path.abspath(os.path.join(build_dir, ".lock"))
    if os.environ.get("PIPELINE_LOCK_HELD") == path:
        yield                                   # a parent process holds it for us
        return
    f = open(path, "a+")
    t0, said = time.time(), False
    try:
        while True:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not said:
                    f.seek(0)
                    log(f"waiting for the pipeline run holding {path} ({f.read().strip() or 'unknown'})")
                    said = True
                if timeout is not None and time.time() - t0 > timeout:
                    raise TimeoutError(f"{path} still locked after {timeout:.0f}s")
                time.sleep(poll)
        f.seek(0)
        f.truncate()
        f.write(f"pid {os.getpid()} since {time.strftime('%H:%M:%S')}\n")
        f.flush()
        os.environ["PIPELINE_LOCK_HELD"] = path
        try:
            yield
        finally:
            os.environ.pop("PIPELINE_LOCK_HELD", None)
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


if __name__ == "__main__":
    import subprocess
    import sys
    args = sys.argv[1:]
    if len(args) < 3 or args[1] != "--":
        sys.exit("usage: python -m pipeline.lock BUILD_DIR -- CMD ...")
    with build_lock(args[0]):
        sys.exit(subprocess.call(args[2:]))
