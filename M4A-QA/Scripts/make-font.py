"""Build a small CJK subset of Source Han Sans SC for the WebGL build.

Collects every non-ASCII character used in shipped content, docs and scripts, then
keeps ASCII plus CJK punctuation/fullwidth blocks so runtime text cannot go blank.
"""
import pathlib, sys, unicodedata

ROOT = pathlib.Path(r"G:\projects\EchoLostAndFound")
SOURCES = [
    ROOT / "Docs",
    ROOT / "M3B",
    ROOT / "EchoLostAndFound_WebGL" / "Assets",
]
SUFFIXES = {".md", ".json", ".cs", ".txt", ".asset"}

chars = set()
for base in SOURCES:
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        if "\\Library\\" in str(path) or "\\Builds\\" in str(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for ch in text:
            if ord(ch) > 0x7E and unicodedata.category(ch)[0] in "LNPSZ":
                chars.add(ch)

extra = "，。、；：？！“”‘’（）《》〈〉【】—…·「」『』～％＆＋－×÷＝〇一二三四五六七八九十百千万亿"
chars.update(extra)

out = ROOT / "M4A-QA" / "Scripts" / "font-chars.txt"
out.write_text("".join(sorted(chars)), encoding="utf-8")
print("unique non-ascii chars:", len(chars))
