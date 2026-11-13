"""python -m isostyle fetch    # download the external datasets and soil pH (once)
python -m isostyle build    # presence and evidence surfaces on the game grid
python -m isostyle pollen   # off-site pollen cores from Neotoma (slow; resumes)
python -m isostyle viewer   # standalone HTML viewer of the build outputs
python -m isostyle gaps [--layer ID ...]   # gap dossiers for the gap critic
python -m isostyle intuitions               # validate the gap critic's intuition files
python -m isostyle speculative              # fill the gaps from the intuitions (for the game)
python -m isostyle evals [--search]         # measure the fill's smoothness and guards; search its settings
python -m isostyle export                   # speculative layers -> evidence_layers.json for neolith-convert
python -m isostyle audit    # Phase 1 data audit (uses isostyle/audit.toml)

--config PATH overrides the config file."""
import argparse
import os
import time
import tomllib


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["fetch", "pollen", "build", "viewer", "gaps", "intuitions", "speculative", "export", "evals", "audit"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--layer", action="append", default=None, help="gaps: layer id (repeatable; default all)")
    ap.add_argument("--min-cells", type=int, default=25, help="gaps: smallest gap reported")
    ap.add_argument("--search", action="store_true", help="evals: search the fill settings")
    ap.add_argument("--check", default=None, metavar="CLAIMS.json", help="evals: test a critic's claims against the numbers")
    ap.add_argument("--crop", nargs=7, default=None, metavar=("LAYER", "YEAR", "LON0", "LAT0", "LON1", "LAT1", "OUT.png"),
                    help="evals: draw one layer, slice and place")
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
    elif args.command == "pollen":
        from . import pollen
        pollen.retry_failed(cfg) if os.path.exists(os.path.join(cfg["output"]["build_dir"], "pollen", "levels.jsonl")) else None
        pollen.fetch(cfg, log)
    elif args.command == "gaps":
        from . import gaps
        gaps.run(cfg, args.layer, min_cells=args.min_cells, log=log)
    elif args.command == "intuitions":
        from . import intuitions
        raise SystemExit(0 if intuitions.run(cfg, log) else 1)
    elif args.command == "speculative":
        from . import speculative
        speculative.run(cfg, log)
    elif args.command == "evals":
        from . import evals
        if args.crop:
            evals.crop(cfg, args.crop[0], int(args.crop[1]), [float(v) for v in args.crop[2:6]], args.crop[6], log)
        elif args.check:
            evals.check(cfg, args.check, log)
        elif args.search:
            evals.search(cfg, log, args.layer)
        else:
            raise SystemExit(0 if evals.run(cfg, log, args.layer) else 1)
    elif args.command == "export":
        from . import export
        export.run(cfg, log)
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
