"""Layer registry (data/isostyle/layers.toml): what each surface is and how to build it."""
import re
import tomllib

KINDS = {"presence_absence", "presence_only", "share", "continuous", "grid"}
UNITS = {"occupation", "core", "sample", "grid"}
# Validated categorical palette (dataviz reference instance), light and dark.
PALETTE = [("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70"), ("#eda100", "#c98500"),
           ("#e87ba4", "#d55181"), ("#008300", "#008300"), ("#6250d6", "#9085e9"), ("#e34948", "#e66767")]
WORD = {"occupation": "occupations", "core": "cores", "sample": "samples", "grid": "grid cells"}


class Registry:
    def __init__(self, data, path="layers.toml"):
        self.groups = list(data.get("groups", []))
        self.layers, seen = [], set()
        slot = {}
        for raw in data.get("layer", []):
            L = dict(raw)
            for k in ("id", "name", "group", "kind"):
                if not L.get(k):
                    raise ValueError(f"{path}: a layer has no {k}")
            if L["id"] in seen:
                raise ValueError(f"{path}: duplicate layer {L['id']!r}")
            seen.add(L["id"])
            if L["kind"] not in KINDS:
                raise ValueError(f"{path}: {L['id']}: unknown kind {L['kind']!r}")
            L.setdefault("unit", "grid" if L["kind"] == "grid" else "occupation")
            if L["unit"] not in UNITS:
                raise ValueError(f"{path}: {L['id']}: unknown unit {L['unit']!r}")
            if L["group"] not in self.groups:
                self.groups.append(L["group"])
            L.setdefault("sigma", "cv")
            L.setdefault("mask", [])
            L.setdefault("levels", [0.25, 0.5, 0.75])
            L.setdefault("licence", "")
            L.setdefault("note", "")
            L.setdefault("set", "")
            if L["kind"] == "share" and not (L.get("prefixes") or L.get("other") or L.get("value_field")):
                raise ValueError(f"{path}: {L['id']}: a share layer needs `prefixes`, `other = true` or `value_field`")
            # fill = false: the speculative step keeps only observed cells (no judged or extrapolated values).
            L.setdefault("fill", True)
            L.setdefault("evidence_word", WORD[L["unit"]])
            L["slug"] = L["id"].replace("_", "-")
            for k in ("site_type", "dated_material"):
                if L.get(k):
                    L[f"{k}_re"] = re.compile(L[k])
            key = L["set"] or L["group"]
            n = slot.get(key, 0)
            slot[key] = n + 1
            # `colour` in the registry overrides the slot colour (the Ancestry
            # set names the colours the game uses for the same components).
            auto = PALETTE[n % len(PALETTE)]
            given = L.get("colour")
            L["colour"] = given or auto[0]
            L["colour_dark"] = L.get("colour_dark") or given or auto[1]
            self.layers.append(L)
        for L in self.layers:
            if L["sigma"] != "cv" and L["sigma"] not in seen:
                raise ValueError(f"{path}: {L['id']}: sigma borrows from unknown layer {L['sigma']!r}")

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            return cls(tomllib.load(f), path)

    def __iter__(self):
        return iter(self.layers)

    def __getitem__(self, lid):
        return next(L for L in self.layers if L["id"] == lid)

    @property
    def ids(self):
        return [L["id"] for L in self.layers]

    def by_unit(self, unit):
        return [L for L in self.layers if L["unit"] == unit]
