
import sys
import os
import re
import json

# Ensure project root (containing src package) is on sys.path
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
PARENT_DIR = os.path.abspath(os.path.join(ROOT_DIR, ".."))
for path in (ROOT_DIR, PARENT_DIR):
    if path not in sys.path:
        sys.path.append(path)

try:
    # Import via the src package so relative imports inside core.py work
    from src.parser.core import parse_capability_log
    from src.model.capability_schema import NormalizedCapability
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

def run_scorecard():
    input_path = "../samples/ue_cap_lte_example.txt" # Using existing sample as a surrogate if input.txt is missing
    # User mentioned input.txt in Samsung PRISM prompt. Let's see if it exists.
    if not os.path.exists("input.txt"):
        # Check parent dir
        if os.path.exists("../input.txt"):
             input_path = "../input.txt"
        elif os.path.exists("samples/ue_cap_lte_example.txt"):
             input_path = "samples/ue_cap_lte_example.txt"
        else:
             print("Could not find input.txt or sample file")
             # Try to find any .txt in samples
             import glob
             txt_files = glob.glob("../samples/*.txt")
             if txt_files:
                 input_path = txt_files[0]
             else:
                 sys.exit(1)

    print(f"Running scorecard on: {input_path}")
    with open(input_path, "r") as f:
        text = f.read()

    cap = parse_capability_log(text, source_file=os.path.basename(input_path))
    
    # We'll just print the relevant fields to verify against the table
    results = {
        "rat": cap.rat,
        "lte_supported_bands_count": len(cap.lte.supported_bands) if cap.lte else 0,
        "lte_supported_bands_list": [b.band for b in cap.lte.supported_bands] if cap.lte else [],
        "lte_ca_combos_count": len(cap.lte.ca_combos) if cap.lte else 0,
        "lte_ue_category_dl": cap.lte.ue_category_dl if cap.lte else None,
        "nr_supported_bands_count": len(cap.nr.supported_bands) if cap.nr else 0,
        "nr_supported_bands_list": [b.band for b in cap.nr.supported_bands] if cap.nr else [],
        "nr_sa_supported": cap.nr.sa_supported if cap.nr else None,
        "nr_nsa_supported": cap.nr.nsa_supported if cap.nr else None,
        "nr_ca_combos_count": len(cap.nr.ca_combos) if cap.nr else 0,
    }
    
    # Band-specific checks (e.g. B41, B260) – only if NR section is present
    if cap.nr and cap.nr.supported_bands:
        b41 = next((b for b in cap.nr.supported_bands if b.band == 41), None)
        if b41:
            results["b41_scs"] = b41.scs_supported
            results["b41_bw"] = b41.max_bw_dl
            results["b41_mimo"] = b41.dl_mimo_layers
            results["b41_qam256"] = b41.dl_256qam

        b260 = next((b for b in cap.nr.supported_bands if b.band == 260), None)
        if b260:
            results["b260_scs"] = b260.scs_supported
            results["b260_bw"] = b260.max_bw_dl
            results["b260_mimo"] = b260.dl_mimo_layers
            results["b260_qam256"] = b260.dl_256qam

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run_scorecard()
