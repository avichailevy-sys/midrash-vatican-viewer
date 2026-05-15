"""
inject_alto_seeAlso.py

Takes a Vatican IIIF v2 manifest and a directory of ALTO files for that
manuscript, and produces a modified manifest where each canvas has a
`seeAlso` entry pointing to its corresponding ALTO file.

Matching strategy: by 4-digit sequence number embedded in both the canvas
@id (e.g., .../canvas/p0003) and the ALTO filename (e.g., _00003_).

USAGE: Place this script in the same folder as:
   - barb_or_1_manifest.json (the original Vatican manifest)
   - all the IM99002497684_*.xml ALTO files
Then open a terminal in that folder and run:
   python inject_alto_seeAlso.py
The modified manifest will be written into the same folder.
"""

import json
import re
from pathlib import Path
from collections import OrderedDict


# === Configuration ==========================================================

# Where the ALTOs will be hosted, with trailing slash.
# When you switch from GitHub Pages to a bigger server later, only this
# changes; the rest of the script is unaffected.
ALTO_BASE_URL = "https://avichailevy-sys.github.io/midrash-vatican-viewer/altos/"

# Format and profile declared in the seeAlso. The textoverlay plugin uses
# these to recognize the file as ALTO v4.
ALTO_FORMAT = "application/alto+xml"
ALTO_PROFILE = "http://www.loc.gov/standards/alto/v4/alto-4-3.xsd"


# === Core logic =============================================================

def extract_sequence_from_canvas(canvas):
    """Extract the 4-digit sequence number from a canvas's @id.

    A canvas @id looks like:
        https://digi.vatlib.it/iiif/MSS_Barb.or.1/canvas/p0003
    We want '0003' (returned as a string to preserve leading zeros).
    """
    canvas_id = canvas["@id"]
    match = re.search(r"/canvas/p(\d+)$", canvas_id)
    if not match:
        return None
    return match.group(1)


def build_alto_index(alto_dir):
    """Scan the ALTO directory and build a dict: sequence_number -> filename.

    ALTO filenames look like:
        IM99002497684_00003_Barb.or.1_0003_cy_0001r.xml
                      ^^^^^
    We extract the first 5-digit number after the IM prefix as the sequence.
    """
    index = {}
    alto_dir = Path(alto_dir)
    for xml_file in alto_dir.glob("*.xml"):
        match = re.match(r"IM\d+_(\d{5})_", xml_file.name)
        if not match:
            continue
        seq = match.group(1)
        # Strip the leading zero from 5-digit ALTO sequence (00003)
        # to match the 4-digit canvas sequence (0003).
        seq_4digit = seq[1:]
        index[seq_4digit] = xml_file.name
    return index


def make_seeAlso(alto_filename):
    """Build a single seeAlso entry pointing to one ALTO file."""
    return {
        "@id": ALTO_BASE_URL + alto_filename,
        "format": ALTO_FORMAT,
        "profile": ALTO_PROFILE,
    }


def inject_seeAlso(manifest, alto_index):
    """Walk through the manifest's canvases and inject seeAlso entries.

    Returns a tuple (modified_manifest, stats_dict).
    """
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
        # Inject as a list, per IIIF convention (seeAlso can hold multiple).
        canvas["seeAlso"] = [make_seeAlso(alto_filename)]
        matched += 1

    stats = {
        "total_canvases": len(canvases),
        "matched": matched,
        "unmatched": unmatched,
        "unmatched_examples": unmatched_examples,
    }
    return manifest, stats


# === Main entry point =======================================================

def main(manifest_path, alto_dir, output_path):
    print(f"Loading manifest from {manifest_path}")
    with open(manifest_path, encoding="utf-8") as f:
        # object_pairs_hook=OrderedDict preserves field ordering, which
        # makes the output diff-friendly against the original.
        manifest = json.load(f, object_pairs_hook=OrderedDict)

    print(f"Scanning ALTOs in {alto_dir}")
    alto_index = build_alto_index(alto_dir)
    print(f"  Found {len(alto_index)} ALTO files")

    print(f"Injecting seeAlso entries")
    manifest, stats = inject_seeAlso(manifest, alto_index)

    print(f"\nStats:")
    print(f"  Total canvases:  {stats['total_canvases']}")
    print(f"  Matched (with ALTO):    {stats['matched']}")
    print(f"  Unmatched (no ALTO):    {stats['unmatched']}")
    if stats["unmatched_examples"]:
        print(f"  Examples of unmatched canvases: {stats['unmatched_examples']}")

    print(f"\nWriting modified manifest to {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print("Done.")


if __name__ == "__main__":
    main(
        manifest_path="barb_or_1_manifest.json",
        alto_dir=".",
        output_path="Barb.or.1_manifest_modified.json",
    )
