
from src.parser.asn_parser import parse_text
import json

text1 = "bandwidthDL : fr1 : mhz100"
text2 = "bandwidthDL fr1 : mhz100"

print("Parsing text1:", text1)
print(json.dumps(parse_text(text1), indent=2))

print("\nParsing text2:", text2)
print(json.dumps(parse_text(text2), indent=2))
