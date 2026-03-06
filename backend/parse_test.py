import sys
import json
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.parser.asn_parser import parse_text

with open(r"c:\Users\DELL\OneDrive\Desktop\Prism1\samples\ue_cap_lte_example.txt", "r") as f:
    text = f.read()

tree = parse_text(text)
print(json.dumps(tree, indent=2))
