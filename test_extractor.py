from backend.src.entry_point import analyze_ue_capability_file
from backend.src.sequential_extractor import sequential_extract

# Step 1: Find entry point
result = analyze_ue_capability_file("samples/UE_Capa.txt")

if result['error']:
    print(f"ERROR in entry_point: {result['error']}")
    exit()

rat_type = result['rat_type']['rat_type_value']
print(f"✓ RAT type detected: {rat_type}")

# Step 2: Extract combinations
with open("samples/UE_Capa.txt", "r") as f:
    content = f.read()

combinations = sequential_extract(content, rat_type)

print(f"✓ Total combinations found: {len(combinations)}")
print(f"\nFirst combination:")
print(combinations[0])