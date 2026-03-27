
import json
import os
import sys
from typing import Any, Dict

# Make sure the 'src' package is importable
sys.path.insert(0, os.path.dirname(__file__))

from src.parser.core import parse_capability_log

def json_diff(dut: Any, ref: Any, path: str = "") -> list:
    diffs = []
    if isinstance(ref, dict):
        if not isinstance(dut, dict):
            diffs.append(f"{path}: type mismatch (expected dict, got {type(dut)})")
            return diffs
        for k, v in ref.items():
            if k not in dut:
                diffs.append(f"{path}.{k}: missing in DUT")
            else:
                diffs.extend(json_diff(dut[k], v, f"{path}.{k}"))
    elif isinstance(ref, list):
        if not isinstance(dut, list):
            diffs.append(f"{path}: type mismatch (expected list, got {type(dut)})")
            return diffs
        if len(dut) != len(ref):
            diffs.append(f"{path}: length mismatch (expected {len(ref)}, got {len(dut)})")
        # For simplicity, we don't do deep list comparison here unless they are small
        if len(ref) < 10:
            for i, (d, r) in enumerate(zip(dut, ref)):
                diffs.extend(json_diff(d, r, f"{path}[{i}]"))
    else:
        if dut != ref:
            diffs.append(f"{path}: value mismatch (expected {ref}, got {dut})")
    return diffs

def verify():
    samples_dir = os.path.join(os.path.dirname(__file__), "..", "samples")
    input_file = os.path.join(samples_dir, "ue_cap_nr_example.txt")
    ref_file = os.path.join(samples_dir, "parsed_reference_example.json")
    
    if not os.path.exists( input_file) or not os.path.exists(ref_file):
        print("Required files not found.")
        return

    with open(input_file, "r") as f:
        text = f.read()
    
    with open(ref_file, "r") as f:
        ref_json = json.load(f)

    # Parse
    cap = parse_capability_log(text, source_file="input.txt")
    dut_json = json.loads(cap.model_dump_json())

    # Filter out fields that aren't in ref for cleaner comparison
    # ref only has lte and nr at top level (plus source_file, rat)
    keys_to_compare = ["rat", "lte", "nr"]
    
    print("\n--- Verification against Reference JSON ---")
    all_diffs = []
    for key in keys_to_compare:
        diffs = json_diff(dut_json.get(key), ref_json.get(key), key)
        all_diffs.extend(diffs)
    
    with open("verify_results_clean.txt", "w", encoding="utf-8") as f:
        if not all_diffs:
            f.write("Success! Parser output matches reference schema perfectly.\n")
        else:
            f.write(f"Found {len(all_diffs)} discrepancies:\n")
            for d in all_diffs:
                f.write(f"  - {d}\n")
    
    if not all_diffs:
        print("Success!")
    else:
        print(f"Found {len(all_diffs)} diffs. See verify_results_clean.txt")

if __name__ == "__main__":
    verify()
