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
            accessStratumRelease rel-14
            ue-Category 6

            rf-Parameters
            {
              supportedBandListEUTRA
              {
                bandEUTRA 3
                bandEUTRA 7
              }
            }

            mimo-Parameters
            {
              maxNumberMIMOLayersDL 2
            }
          }
        }

        RAT-Type nr
        ueCapabilityRAT-Container
        {
          UE-NR-Capability
          {
            accessStratumRelease rel-15

            supportedBandListNR
            {
              bandNR n78
            }

            mimo-ParametersNR
            {
              maxNumberMIMOLayersDL 2
            }

            nr-SA supported TRUE
            nr-NSA supported FALSE
          }
        }
      }
    }
  }
}'''

tree = parse_text(LOG)

def show(obj, indent=0, max_depth=6):
    prefix = "  " * indent
    if indent > max_depth:
        print(prefix + "...")
        return
    if isinstance(obj, dict):
        for k, v in list(obj.items())[:30]:
            if isinstance(v, dict):
                print(f"{prefix}{k}:")
                show(v, indent+1, max_depth)
            elif isinstance(v, list):
                print(f"{prefix}{k}: [{len(v)} items]")
                for item in v[:3]:
                    show(item, indent+1, max_depth)
            else:
                print(f"{prefix}{k}: {v!r}")
    else:
        print(f"{prefix}{obj!r}")

show(tree)
