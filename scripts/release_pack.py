#!/usr/bin/env python3
"""Check a built Frames pack against the pack it replaces, then write the release ZIP.

A release may add frames. It must not change anything that already shipped,
because the Apple Frames shortcut and older CLIs read the same pack. This
script copies the built pack to a new folder, sets version.txt, and stops unless:

- every file of the previous pack is present and byte-identical (NewFrames.json
  and version.txt aside);
- every new file is a readable PNG that belongs to one of the added variants;
- NewFrames.json, with the added variants removed, is byte-identical to the
  previous catalog.

The ZIP comes from write_archive, which wrote every published pack, so the
same folder always gives the same bytes. Neither input is modified. Requires
Pillow.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_duo_assets import write_archive  # noqa: E402

CATALOG, VERSION = "NewFrames.json", "version.txt"


def read_pack(path):
    """Map file names to bytes for a pack folder or a published pack ZIP."""
    if path.is_dir():
        if any(item.is_dir() for item in path.iterdir()):
            raise ValueError("Pack folder has a subfolder: {}".format(path))
        return {item.name: item.read_bytes() for item in path.iterdir() if not item.name.startswith(".")}
    with zipfile.ZipFile(str(path)) as archive:
        names = archive.namelist()
        if any(not name.startswith("Frames/") or name.count("/") != 1 for name in names):
            raise ValueError("Expected every ZIP member directly under Frames/: {}".format(path))
        return {name.split("/", 1)[1]: archive.read(name) for name in names}


def dump_catalog(catalog):
    """Serialize a catalog the way every pack builder writes NewFrames.json."""
    return (json.dumps(catalog, indent=2) + "\n").encode("utf-8")


def reject_constant(value):
    raise ValueError("NewFrames.json contains {}, which is not valid JSON".format(value))


def check_pack(built, base, added):
    """Raise ValueError unless built is base plus the added variants and their PNGs."""
    for name in (CATALOG, VERSION):
        if name not in base or name not in built:
            raise ValueError("Both packs need {}".format(name))
    missing = sorted(set(base) - set(built))
    if missing:
        raise ValueError("Missing from the new pack: {}".format(", ".join(missing)))
    changed = sorted(name for name in base if name not in (CATALOG, VERSION) and base[name] != built[name])
    if changed:
        raise ValueError("Changed since the previous pack: {}".format(", ".join(changed)))

    # The shortcut parses this file on every run, so it must stay strict JSON.
    catalog = json.loads(built[CATALOG].decode("utf-8"), parse_constant=reject_constant)
    if dump_catalog(catalog) != built[CATALOG]:
        raise ValueError("NewFrames.json is not written as json.dumps(catalog, indent=2) plus a newline")
    previous = json.loads(base[CATALOG].decode("utf-8"))
    new_variants = [name for name in catalog["variants"] if name not in previous["variants"]]
    if sorted(new_variants) != sorted(added):
        raise ValueError("Expected added variants {}, found {}".format(sorted(added), sorted(new_variants)))
    for name in added:
        if catalog["variants"][name].get("name") != name:
            raise ValueError("Variant {} has a different name field".format(name))
    stripped = dict(catalog, variants={k: v for k, v in catalog["variants"].items() if k not in added})
    if dump_catalog(stripped) != base[CATALOG]:
        raise ValueError("NewFrames.json changes more than the added variants")

    new_files = sorted(set(built) - set(base))
    for name in new_files:
        owners = [variant for variant in added if name.startswith((variant + " ", variant + "_", variant + "."))]
        if not name.endswith(".png") or not owners:
            raise ValueError("New file does not belong to an added variant: {}".format(name))
        with Image.open(io.BytesIO(built[name])) as image:
            image.verify()
    for variant in added:
        if not any(name.startswith(variant) for name in new_files):
            raise ValueError("No new files for {}".format(variant))
    return new_files


def release_pack(built_path, base_path, version, added, output, archive):
    """Write the versioned pack folder and its ZIP; return a summary."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Version must look like 4.2.2")
    for path in (output, archive):
        if path.exists():
            raise ValueError("Destination must not exist: {}".format(path))
    built, base = read_pack(built_path), read_pack(base_path)
    previous_version = base[VERSION].decode("utf-8")
    if previous_version == version:
        raise ValueError("The previous pack is already version {}".format(version))
    new_files = check_pack(built, base, added)

    output.mkdir(parents=True)
    for name, data in built.items():
        (output / name).write_bytes(data)
    # No trailing newline: the Apple Frames shortcut compares this text exactly.
    (output / VERSION).write_text(version, encoding="utf-8")
    write_archive(output, archive)
    data = archive.read_bytes()
    return {
        "version": version, "previous_version": previous_version,
        "files": len(built), "pngs": sum(name.endswith(".png") for name in built),
        "new_files": new_files, "unchanged_files": len(base) - 2,
        "archive": str(archive), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("built", type=Path, help="Built pack folder (read-only)")
    parser.add_argument("--base", required=True, type=Path, help="Previous pack: its published ZIP or a folder")
    parser.add_argument("--version", required=True, help="version.txt for the new pack, such as 4.2.2")
    parser.add_argument("--added", required=True, action="append", metavar="VARIANT",
                        help="Variant the new catalog adds; repeat for each one")
    parser.add_argument("--output", required=True, type=Path, help="New folder for the versioned pack")
    parser.add_argument("--archive", required=True, type=Path, help="New ZIP file, such as AppleFrames422.zip")
    args = parser.parse_args()
    try:
        summary = release_pack(args.built, args.base, args.version, args.added, args.output, args.archive)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, SyntaxError) as error:
        parser.exit(1, "Error: {}\n".format(error))
    print("Pack {version} (was {previous_version}): {files} files, {pngs} PNGs".format(**summary))
    print("Unchanged from {}: {} files, byte-identical".format(summary["previous_version"], summary["unchanged_files"]))
    print("New files ({}):".format(len(summary["new_files"])))
    for name in summary["new_files"]:
        print("  " + name)
    print("{}: {:,} bytes ({})".format(args.archive.name, summary["bytes"], summary["bytes"]))
    print("SHA-256: {}".format(summary["sha256"]))


if __name__ == "__main__":
    main()
