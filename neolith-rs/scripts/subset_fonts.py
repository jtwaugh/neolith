"""Make the web-sized EB Garamond fonts that the app compiles in.

The source fonts in crates/app/assets/fonts are variable fonts (wght 400-800,
~800 KB each). egui only renders a font's default instance, so this freezes
each one at wght=400, the default, then subsets it to the Latin scripts and
punctuation that map labels use. egui falls back to its own fonts for any
glyph that's missing.

    python3 scripts/subset_fonts.py      (needs fonttools: pip install fonttools)
"""

from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

FONTS = Path(__file__).resolve().parent.parent / "crates/app/assets/fonts"

UNICODES = [
    *range(0x0020, 0x007F),  # Basic Latin
    *range(0x00A0, 0x0250),  # Latin-1 Supplement, Latin Extended-A and -B
    *range(0x0300, 0x0370),  # combining diacritics
    *range(0x1E00, 0x1F00),  # Latin Extended Additional
    *range(0x2000, 0x2070),  # General Punctuation
    0x2212,  # minus sign
]


def main() -> None:
    for name in ["EBGaramond", "EBGaramond-Italic"]:
        src = FONTS / f"{name}.ttf"
        out = FONTS / f"{name}.subset.ttf"
        font = instancer.instantiateVariableFont(TTFont(src), {"wght": 400})
        options = subset.Options()
        # pyftsubset's default layout features: the ones shaping needs
        # (kern, liga, mark, ...). egui shapes with harfrust, so keep them.
        options.hinting = False
        options.name_IDs = ["*"]  # keep the copyright and licence names (OFL)
        subsetter = subset.Subsetter(options)
        subsetter.populate(unicodes=UNICODES)
        subsetter.subset(font)
        font.save(out)
        print(f"{out.name}: {src.stat().st_size:,} -> {out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
