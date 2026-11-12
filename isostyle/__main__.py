"""python -m isostyle fetch    # download the external datasets and soil pH (once)
python -m isostyle build    # presence and evidence surfaces on the game grid
python -m isostyle viewer   # standalone HTML viewer of the build outputs
python -m isostyle audit    # Phase 1 data audit (uses isostyle/audit.toml)

--config PATH overrides the config file."""
import argparse
import time
import tomllib


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["fetch", "build", "viewer", "audit"])
    ap.add_argument("--config", default=None)
    args = ap.parse_args()
    path = args.config or ("isostyle/audit.toml" if args.command == "audit" else "isostyle/config.toml")
    cfg = tomllib.load(open(path, "rb"))
    t0 = time.time()

    def log(msg):
        print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    if args.command == "audit":
        from . import audit
        audit.run(cfg, log)
    elif args.command == "fetch":
        from . import fetch
        fetch.run(cfg, log)
    elif args.command == "viewer":
        from . import viewer
        viewer.run(cfg, log)
    else:
        from . import build, fetch, viewer
        fetch.run(cfg, log)
        build.run(cfg, log)
        viewer.run(cfg, log)


if __name__ == "__main__":
    main()
