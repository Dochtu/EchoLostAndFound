"""Refresh R1 manifests and build a verified incremental ZIP on top of the M1.5 delivery.

Run with --manifests-only during production. The default command also archives
R1 reports, evidence, the two manifests and an index of SHA-256 values.
"""
import argparse
import csv
import hashlib
import io
from pathlib import Path
import re
import struct
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile
import zlib


ROOT = Path(__file__).resolve().parents[2]
ROOTS = ("Assets", "Packages", "ProjectSettings", "Tools")
BASELINE = ROOT / "Library/R1Baseline/source.zip"
PREVIOUS = ROOT / "Stage4_M1_5_VisualUpgrade_Delivery.zip"
ARCHIVE = ROOT / "Stage4_M1_5_R1_Delivery.zip"
MANIFEST = "Docs/M1_5_R1_AssetManifest.csv"
LICENSES = "Docs/M1_5_R1_FreeAssetManifest.csv"
EVIDENCE = "Docs/Evidence/M1_5_R1"
INDEX = "SHA256SUMS.txt"
ENV_TOOL = "Tools/M1_5/build_r1_environment.py"
NPC_TOOL = "Tools/M1_5/refine_r1_character.py"
CC0_FLOOR = "Assets/_Project/Art/Textures/M1_5/Terrazzo/Base.jpg"
FEE_FIELDS = ("AssetName", "AssetPath", "SourceURL", "Author", "LicenseType", "CommercialUse",
              "AttributionRequired", "AttributionText", "DownloadDate", "IsAIgenerated",
              "IsSelfCreated", "IsPlaceholder")
FIELDS = ("AssetPath", "Change", "InDelivery", "PreviousSHA256", "DigestSHA256", "SizeBytes",
          "AssetType", "GUID", "MetaPath", "TextureResolution", "TriangleCount", "Source", "Notes")
GUID = re.compile(rb"(?m)^guid:\s*([0-9a-f]{32})\s*$")
OBJECT_GUID = re.compile(rb"guid:\s*([0-9a-f]{32})")
TEXTURE_ROOT = "Assets/_Project/Art/Textures/M1_5/"
PROJECT = "EchoLostAndFound"


def digest(stream):
    h = hashlib.sha256()
    for part in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(part)
    return h.hexdigest()


def disk_hash(name):
    with (ROOT / name).open("rb") as f:
        return digest(f)


def write_atomic(path, contents):
    if path.is_file() and path.read_bytes() == contents:
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        try:
            f.write(contents)
            f.close()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def csv_bytes(fields, rows):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fields)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def from_archives(baseline_path, previous_path):
    with ZipFile(baseline_path) as baseline, ZipFile(previous_path) as previous:
        with io.TextIOWrapper(previous.open("Docs/M1_5_FreeAssetManifest.csv"), encoding="utf-8-sig") as f:
            sources = {}
            for row in csv.DictReader(f):
                sources.setdefault(row["AssetPath"], []).append({k: row[k] for k in FEE_FIELDS})
        prior = {}
        for info in baseline.infolist():
            if info.is_dir() or info.filename.split("/")[0] not in ROOTS:
                continue
            with baseline.open(info) as f:
                prior[info.filename] = digest(f)
        # The complete pre-R1 snapshot supplies unchanged dependencies missing
        # from the M1.5 patch. Verify their overlapping project payload, too.
        for info in previous.infolist():
            if info.is_dir() or info.filename.split("/")[0] not in ROOTS:
                continue
            with previous.open(info) as f:
                if prior.get(info.filename) != digest(f):
                    raise ValueError("M1.5 archive disagrees with the R1 baseline: " + info.filename)
    return prior, sources


def exclude_reason(name):
    if name == "Assets/_Recovery.meta" or name.startswith("Assets/_Recovery/"):
        return "Unity recovery copy outside the production scene."
    if name == "ProjectSettings/Packages/com.unity.probuilder/Settings.json":
        return "Local ProBuilder editor state."
    if name.startswith(("Assets/Settings/", "ProjectSettings/", "Packages/")):
        return "Shared project or render configuration outside the R1 delivery scope."
    if name == "Assets/SourceHanSansSC-Regular SDF.asset":
        return "Existing dynamically updated font atlas. The project already supplies the font."
    return ""


def inventory(prior):
    current = {}
    guid_paths = {}
    for top in ROOTS:
        for path in (ROOT / top).rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            name = path.relative_to(ROOT).as_posix()
            current[name] = disk_hash(name)
            if path.suffix == ".meta" and top == "Assets":
                with path.open("rb") as f:
                    match = GUID.search(f.read(1024))
                if match:
                    guid = match[1].decode()
                    if guid in guid_paths:
                        raise ValueError("Duplicate Unity GUID: " + guid)
                    guid_paths[guid] = name[:-5]
    changes = {}
    for name in sorted(prior.keys() | current.keys()):
        if current.get(name) == prior.get(name):
            continue
        changes[name] = "Removed" if name not in current else "Added" if name not in prior else "Modified"
    # Include the unchanged companion for an edited existing asset or importer,
    # plus the Unity metas of its containing folders. Preserve their GUIDs.
    for name, change in list(changes.items()):
        if change == "Removed" or exclude_reason(name) or not name.startswith("Assets/"):
            continue
        raw = name[:-5] if name.endswith(".meta") else name
        candidates = [raw+".meta"]
        if (ROOT / raw).is_file():
            candidates.append(raw)
        for parent in Path(raw).parents:
            if len(parent.parts) < 2:
                break
            candidates.append(parent.as_posix()+".meta")
        for candidate in candidates:
            if candidate not in current:
                raise FileNotFoundError("Unity companion missing: "+candidate)
            changes.setdefault(candidate,"Companion")
    return current, changes, guid_paths


def triangles(path):
    """Count triangulated mesh faces from the FBX PolygonVertexIndex streams."""
    data = path.read_bytes()
    if not data.startswith(b"Kaydara FBX Binary"):
        return ""
    version = struct.unpack_from("<I",data,23)[0]
    fmt = "<QQQB" if version >= 7500 else "<IIIB"
    head = struct.calcsize(fmt)
    total = 0

    def visit(start, end):
        nonlocal total
        pos = start
        while pos + head <= end:
            stop, _, prop_bytes, n = struct.unpack_from(fmt,data,pos)
            if stop == 0:
                break
            if not pos < stop <= end:
                raise ValueError("Invalid FBX node in " + str(path))
            pos += head
            key = data[pos:pos+n]
            props = pos+n
            if key == b"PolygonVertexIndex":
                if data[props:props+1] != b"i":
                    raise ValueError("Unsupported FBX mesh index format")
                count, compressed, size = struct.unpack_from("<III",data,props+1)
                block = data[props+13:props+13+size]
                if compressed:
                    block = zlib.decompress(block)
                if len(block) != count*4:
                    raise ValueError("FBX mesh index count mismatch")
                total += count-2*sum(x[0]<0 for x in struct.iter_unpack("<i",block))
            elif key in (b"Objects", b"Geometry"):
                visit(props+prop_bytes,stop)
            pos = stop
    visit(27,len(data))
    return total


def licence(name, title=None, source=""):
    return dict(zip(FEE_FIELDS,(title or Path(name).stem,name,source,PROJECT,"Project original","Yes","No","","","No","Yes","No")))


def lineage(name, old, guid_paths):
    path = ROOT / name
    inherited = [dict(r) for r in old.get(name, [])]
    if name.endswith("/R1MutedTerrazzo.png"):
        rows = [dict(r, AssetName="R1 muted terrazzo / "+r["AssetName"], AssetPath=name)
                for r in old[CC0_FLOOR]]
        return ENV_TOOL+" | "+CC0_FLOOR, rows, "Lower-contrast adaptation of ambientCG Terrazzo001."
    if name.endswith("/R1WetApronMask.png"):
        return ENV_TOOL, [licence(name,source=ENV_TOOL)], "Project-authored packed wetness gradient."
    if name.endswith("/StationVisitor.fbx"):
        if not inherited:
            raise ValueError("Missing original visitor component licences.")
        inherited.append(licence(name,"R1 visitor fitting, hair and idle refinements",NPC_TOOL))
        return NPC_TOOL+" | "+PREVIOUS.name+"!/"+name, inherited, "Preserves the original MakeHuman component licences."
    if path.suffix == ".mat":
        refs = sorted({guid_paths[m.decode()] for m in OBJECT_GUID.findall(path.read_bytes())
                       if m.decode() in guid_paths})
        source = " | ".join(refs)
        return source or "Project HDRP material", inherited or [licence(name)], "Project material; referenced resources retain individual licences."
    if path.suffix == ".fbx" and path.stem in ("R1HallThreshold","R1RailBoundary"):
        return ENV_TOOL,[licence(name,source=ENV_TOOL)],"Blender-authored environment module."
    if inherited:
        return PREVIOUS.name+"!/"+name, inherited, "Prior M1.5 project source with R1 revisions."
    if path.suffix in (".cs",".py",".unity",".prefab",".controller"):
        return "Project authoring", [licence(name)], ""
    raise ValueError("A source record is needed for this new asset: "+name)


def manifests(baseline, previous):
    prior, old = from_archives(baseline,previous)
    current, changes, guid_paths = inventory(prior)
    reverse = {name:guid for guid,name in guid_paths.items()}
    rows, free, payload = [], [], {}
    for name,change in sorted(changes.items()):
        path = ROOT/name
        reason = exclude_reason(name)
        included = name in current and not reason
        row = dict.fromkeys(FIELDS,"")
        row.update(AssetPath=name, Change=change, InDelivery="Yes" if included else "No",
                   PreviousSHA256=prior.get(name,""), DigestSHA256=current.get(name,""),
                   AssetType=path.suffix.lstrip("."), Notes=reason)
        if name in current:
            row["SizeBytes"] = path.stat().st_size
        if included:
            payload[name] = current[name]
            if path.suffix == ".meta":
                row.update(Source="Unity asset/folder importer",GUID=reverse.get(name[:-5],""))
            else:
                source, fees, notes = lineage(name,old,guid_paths)
                row.update(Source=source,Notes=notes,GUID=reverse.get(name,""))
                free.extend(fees)
                if name.startswith("Assets/"):
                    row["MetaPath"] = name+".meta"
                if path.suffix == ".fbx":
                    row["TriangleCount"] = triangles(path)
                if path.suffix == ".png":
                    with path.open("rb") as f:
                        w,h = struct.unpack(">II",f.read(24)[16:24])
                    row["TextureResolution"] = f"{w}x{h}"
        rows.append(row)
    write_atomic(ROOT/MANIFEST,csv_bytes(FIELDS,rows))
    write_atomic(ROOT/LICENSES,csv_bytes(FEE_FIELDS,free))
    print(f"Inventory: {len(rows)} file records, {len(free)} source records, {len(payload)} project files to deliver.")
    return payload


def package(payload, output):
    for path in (ROOT/EVIDENCE).rglob("*"):
        if path.is_file():
            name = path.relative_to(ROOT).as_posix()
            payload[name] = disk_hash(name)
    for path in sorted((ROOT/"Docs").glob("M1_5_R1*.md")):
        name = path.relative_to(ROOT).as_posix()
        payload[name] = disk_hash(name)
    for name in (MANIFEST, LICENSES):
        payload[name] = disk_hash(name)
    sums = "".join(f"{value}  {name}\n" for name,value in sorted(payload.items())).encode("utf-8")
    expected = {**payload, INDEX:hashlib.sha256(sums).hexdigest()}
    with NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as f:
        staged = Path(f.name)
    try:
        with ZipFile(staged,"w",ZIP_DEFLATED,compresslevel=4,allowZip64=True) as z:
            for name in sorted(payload):
                z.write(ROOT/name,name)
            z.writestr(INDEX,sums)
        with ZipFile(staged) as z:
            if len(z.namelist()) != len(expected) or set(z.namelist()) != set(expected):
                raise ValueError("ZIP membership mismatch")
            for name,value in expected.items():
                with z.open(name) as stream:
                    if digest(stream) != value:
                        raise ValueError("ZIP entry changed while packaging: "+name)
        staged.replace(output)
    finally:
        staged.unlink(missing_ok=True)
    with output.open("rb") as f:
        print(f"Verified {len(expected)} members, {output.stat().st_size} bytes. {output.name} SHA-256 {digest(f)}")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--manifests-only", action="store_true")
    cli.add_argument("--baseline", type=Path, default=BASELINE)
    cli.add_argument("--previous", type=Path, default=PREVIOUS)
    cli.add_argument("--output", type=Path, default=ARCHIVE)
    args = cli.parse_args()
    files = manifests(args.baseline,args.previous)
    if not args.manifests_only:
        package(files,args.output)
