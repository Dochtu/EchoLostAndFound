from fontTools.ttLib import TTFont
f = TTFont(r"G:\projects\EchoLostAndFound\EchoLostAndFound_WebGL\Assets\_Project\Resources\M4A\StationChinese.otf")
for rec in f["name"].names:
    try:
        val = rec.toUnicode()
    except Exception as exc:
        val = "<decode error %s>" % exc
    print("nameID", rec.nameID, "plat", rec.platformID, rec.platEncID, "lang", rec.langID, "->", val.encode("unicode_escape").decode("ascii"))
print("numGlyphs", f["maxp"].numGlyphs, "cmap", [(t.platformID,t.platEncID,t.format) for t in f["cmap"].tables])
