"""
inject_alto_seeAlso.py

Takes a Vatican IIIF v2 manifest and a directory of ALTO files for that
manuscript, and produces a modified manifest where each canvas has a
`seeAlso` entry pointing to its corresponding ALTO file.

USAGE:
    python inject_alto_seeAlso.py <manuscript_name>

EXAMPLE:
    python inject_alto_seeAlso.py Barb.or.1
    python inject_alto_seeAlso.py Vat.ebr.108
    python inject_alto_seeAlso.py Vat.ebr.23

The script expects a folder structure like:
    <manuscript_name>/
        original_manifest.json   (input: Vatican's manifest, downloaded by user)
        altos/                   (input: directory containing the ALTO XMLs)
            IM..._00001_...xml
            IM..._00002_...xml
            ...

It produces:
    <manuscript_name>/
        manifest.json            (output: modified manifest with seeAlso entries)

Matching strategy: by 4-digit sequence number embedded in both the canvas
@id (e.g., .../canvas/p0003) and the ALTO filename (e.g., _00003_).
"""

import json
import re
import sys
from pathlib import Path
from collections import OrderedDict


# === Configuration ==========================================================

# Where the project is hosted on GitHub Pages. Per-manuscript URLs are built
# by appending the manuscript name and the ALTO subpath.
SITE_BASE_URL = "https://avichailevy-sys.github.io/midrash-vatican-viewer"

# Format and profile declared in the seeAlso. The textoverlay plugin uses
# these to recognize the file as ALTO v4.
ALTO_FORMAT = "application/alto+xml"
ALTO_PROFILE = "http://www.loc.gov/standards/alto/v4/alto-4-3.xsd"


# === Core logic =============================================================

def extract_sequence_from_canvas(canvas):
    """Extract the 4-digit sequence number from a canvas's @id."""
    canvas_id = canvas["@id"]
    match = re.search(r"/canvas/p(\d+)$", canvas_id)
    if not match:
        return None
    return match.group(1)


def build_alto_index(alto_dir):
    """Scan the ALTO directory; return dict: sequence_number -> filename."""
    index = {}
    alto_dir = Path(alto_dir)
    for xml_file in alto_dir.glob("*.xml"):
        match = re.match(r"IM\d+_(\d{5})_", xml_file.name)
        if not match:
            continue
        seq = match.group(1)
        # Strip leading zero from 5-digit sequence to match 4-digit canvas id.
        seq_4digit = seq[1:]
        index[seq_4digit] = xml_file.name
    return index


def make_seeAlso(alto_filename, manuscript_name):
    """Build a seeAlso entry pointing to one ALTO file."""
    url = f"{SITE_BASE_URL}/{manuscript_name}/altos/{alto_filename}"
    return {
        "@id": url,
        "format": ALTO_FORMAT,
        "profile": ALTO_PROFILE,
    }


def inject_seeAlso(manifest, alto_index, manuscript_name):
    """Walk through canvases; inject seeAlso into matched ones."""
    canvases = manifest["sequences"][0]["canvases"]
    matched = 0
    unmatched = 0
    unmatched_examples = []

    for canvas in canvases:
        seq = extract_sequence_from_canvas(canvas)
        if seq is None:
            unmatched += 1
            continue
        if seq not in alto_index:
            unmatched += 1
            if len(unmatched_examples) < 5:
                unmatched_examples.append(canvas["@id"].split("/")[-1])
            continue
        alto_filename = alto_index[seq]
        canvas["seeAlso"] = [make_seeAlso(alto_filename, manuscript_name)]
        matched += 1

    stats = {
        "total_canvases": len(canvases),
        "matched": matched,
        "unmatched": unmatched,
        "unmatched_examples": unmatched_examples,
    }
    return manifest, stats


# === Main entry point =======================================================

def main(manuscript_name):
    manuscript_dir = Path(manuscript_name)
    manifest_path = manuscript_dir / "original_manifest.json"
    alto_dir = manuscript_dir / "altos"
    output_path = manuscript_dir / "manifest.json"

    if not manuscript_dir.is_dir():
        print(f"ERROR: Manuscript folder '{manuscript_name}' not found.")
        print(f"  Looked for: {manuscript_dir.resolve()}")
        sys.exit(1)
    if not manifest_path.is_file():
        print(f"ERROR: Original manifest not found.")
        print(f"  Looked for: {manifest_path.resolve()}")
        sys.exit(1)
    if not alto_dir.is_dir():
        print(f"ERROR: ALTOs folder not found.")
        print(f"  Looked for: {alto_dir.resolve()}")
        sys.exit(1)

    print(f"=== Processing manuscript: {manuscript_name} ===")
    print(f"Loading manifest from {manifest_path}")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f, object_pairs_hook=OrderedDict)

    print(f"Scanning ALTOs in {alto_dir}")
    alto_index = build_alto_index(alto_dir)
    print(f"  Found {len(alto_index)} ALTO files")

    print(f"Injecting seeAlso entries")
    manifest, stats = inject_seeAlso(manifest, alto_index, manuscript_name)

    print(f"\nStats:")
    print(f"  Total canvases:        {stats['total_canvases']}")
    print(f"  Matched (with ALTO):   {stats['matched']}")
    print(f"  Unmatched (no ALTO):   {stats['unmatched']}")
    if stats["unmatched_examples"]:
        print(f"  Examples of unmatched: {stats['unmatched_examples']}")

    print(f"\nWriting modified manifest to {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print("Done.\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python inject_alto_seeAlso.py <manuscript_name>")
        print("Example: python inject_alto_seeAlso.py Vat.ebr.108")
        sys.exit(1)
    main(sys.argv[1])
