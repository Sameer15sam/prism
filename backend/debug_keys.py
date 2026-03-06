import sys, json
sys.path.insert(0, '.')

from src.parser.asn_parser import parse_text

LOG = '''DL-DCCH-Message
{
  message c1 : ueCapabilityInformation
  {
    rrc-TransactionIdentifier 1
    criticalExtensions c1 : ueCapabilityInformation-r8
    {
      ue-CapabilityRAT-ContainerList
      {
        RAT-Type eutra
        ueCapabilityRAT-Container
        {
          UE-EUTRA-Capability
          {
            ue-Category 6
            rf-Parameters
            {
              supportedBandListEUTRA
              {
                bandEUTRA 3
                bandEUTRA 7
              }
            }
          }
        }

        RAT-Type nr
        ueCapabilityRAT-Container
        {
          UE-NR-Capability
          {
            supportedBandListNR
            {
              bandNR n78
            }
          }
        }
      }
    }
  }
}'''

tree = parse_text(LOG)

def dump_keys(obj, path="root", depth=0):
    if depth > 8:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_path = f"{path}.{k}"
            if isinstance(v, dict):
                print(f"DICT  {full_path}")
                dump_keys(v, full_path, depth+1)
            elif isinstance(v, list):
                print(f"LIST  {full_path} [{len(v)} items]")
                for i, item in enumerate(v[:2]):
                    dump_keys(item, f"{full_path}[{i}]", depth+1)
            else:
                print(f"VAL   {full_path} = {v!r}")

dump_keys(tree)
print()
print("--- NORMALIZED KEYS at each level ---")

def dump_norm(obj, path="root", depth=0):
    if depth > 8:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            nk = k.lower().replace('-','_').replace(' ','_')
            full_path = f"{path}.{nk}"
            if isinstance(v, dict):
                print(f"DICT  {full_path}")
                dump_norm(v, full_path, depth+1)
            elif isinstance(v, list):
                print(f"LIST  {full_path} [{len(v)}]")
                for i, item in enumerate(v[:2]):
                    dump_norm(item, f"{full_path}[{i}]", depth+1)
            else:
                print(f"VAL   {full_path} = {v!r}")

dump_norm(tree)
