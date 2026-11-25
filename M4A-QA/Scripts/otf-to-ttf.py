"""Convert the fonttools CFF subset to a TrueType outline font Unity can import.

Unity's TrueTypeFontImporter produces an empty Font asset for the CFF-flavoured
subset (no font names, no glyphs), which makes TMP_FontAsset.CreateFontAsset
return a font asset without any characters. Converting the outlines to `glyf`
gives Unity a regular TrueType file.
"""
from otf2ttf.cli import otf_to_ttf
from fontTools.ttLib import TTFont

SOURCE = r"G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL\Assets\_Project\Resources\M4A\StationChinese.otf"
TARGET = r"G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL\Assets\_Project\Resources\M4A\StationChinese.ttf"

font = TTFont(SOURCE)
otf_to_ttf(font, max_err=1.0)
font.save(TARGET)

check = TTFont(TARGET)
print("tables:", sorted(check.keys()))
print("glyphs:", check["maxp"].numGlyphs, "glyf:", "glyf" in check, "cmap:", [(t.platformID, t.platEncID, t.format) for t in check["cmap"].tables])
print("family:", check["name"].getDebugName(1), "full:", check["name"].getDebugName(4))
