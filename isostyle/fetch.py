"""Download the external presence datasets and the soil-pH rasters once.

Each [[sources]] entry in the config names a repository record and a
filename pattern. Files land in [output] build_dir/sources/ and are listed,
with URL, size and SHA-256, in sources/provenance.json. A file that is
already there is not fetched again.
"""
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "isostyle-pipeline/0.1 (research script)"}


def _get(url, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(3 * (k + 1))


def resolve(spec):
    """The download URL for a source entry."""
    kind = spec["kind"]
    if kind == "url":
        return spec["url"]
    if kind == "zenodo":
        rec = json.loads(_get(f"https://zenodo.org/api/records/{spec['id']}"))
        for f in rec["files"]:
            if re.search(spec["match"], f["key"]):
                return f["links"]["self"]
    elif kind == "nakala":
        rec = json.loads(_get(f"https://api.nakala.fr/datas/{spec['id']}"))
        for f in rec["files"]:
            if re.search(spec["match"], f["name"]):
                return f"https://api.nakala.fr/data/{spec['id']}/{f['sha1']}"
    elif kind == "github":
        tree = json.loads(_get(f"https://api.github.com/repos/{spec['id']}/git/trees/HEAD?recursive=1"))
        for f in tree["tree"]:
            if re.search(spec["match"], f["path"]):
                return f"https://raw.githubusercontent.com/{spec['id']}/HEAD/{urllib.parse.quote(f['path'])}"
    raise LookupError(f"{spec['name']}: nothing matches {spec.get('match')!r} in {kind} record {spec.get('id')}")


def run(cfg, log=print):
    d = os.path.join(cfg["output"]["build_dir"], "sources")
    os.makedirs(d, exist_ok=True)
    ppath = os.path.join(d, "provenance.json")
    prov = json.load(open(ppath)) if os.path.exists(ppath) else {}
    for spec in cfg["sources"]:
        path = os.path.join(d, spec["file"])
        if os.path.exists(path) and spec["file"] in prov:
            continue
        if spec["kind"] == "manual":
            # Downloaded by hand (the host refuses scripted downloads).
            if not os.path.exists(path):
                log(f"fetch {spec['name']}: download {spec['url']} by hand into {d}/")
                continue
            data = open(path, "rb").read()
            prov[spec["file"]] = {"name": spec["name"], "url": spec["url"], "bytes": len(data),
                                  "sha256": hashlib.sha256(data).hexdigest(), "retrieved": "manual download",
                                  "recorded": time.strftime("%Y-%m-%d")}
            json.dump(prov, open(ppath, "w"), indent=1)
            continue
        try:
            url = resolve(spec)
            data = _get(url)
        except Exception as e:  # the build reports and skips a missing source
            log(f"fetch {spec['name']}: FAILED ({e})")
            continue
        with open(path, "wb") as f:
            f.write(data)
        prov[spec["file"]] = {"name": spec["name"], "url": url, "bytes": len(data),
                              "sha256": hashlib.sha256(data).hexdigest(),
                              "retrieved": time.strftime("%Y-%m-%d")}
        log(f"fetch {spec['name']}: {len(data)} bytes")
        json.dump(prov, open(ppath, "w"), indent=1)
    return prov
