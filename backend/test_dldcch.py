import sys
import pathlib

sys.path.insert(0, '.')

from src.parser.core import parse_capability_log

# The exact format from the user's report
DL_DCCH_LOG = '''DL-DCCH-Message
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

            featureGroupIndicators
            {
              fgiBit1 TRUE
              fgiBit3 TRUE
              fgiBit7 FALSE
            }

            pdsch-Parameters
            {
              supportedModulation QPSK
              supportedModulation 16QAM
            }

            mimo-Parameters
            {
              maxNumberMIMOLayersDL 2
            }

            ca-Parameters
            {
              supported FALSE
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

            pdsch-ParametersNR
            {
              supportedModulation QPSK
              supportedModulation 16QAM
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

print("=== Parsing DL-DCCH-Message Format ===")
cap = parse_capability_log(DL_DCCH_LOG, "dl_dcch_test.txt")
print(f"RAT:  {cap.rat}")
print()

if cap.lte:
    print("LTE:")
    print(f"  UE Category: {cap.lte.ue_category_dl}")
    print(f"  Bands: {[b.band for b in cap.lte.supported_bands]}")
    for b in cap.lte.supported_bands:
        print(f"    Band {b.band}: type={b.band_type} dl_mimo={b.dl_mimo_layers}")
else:
    print("LTE: NOT DETECTED")

print()

if cap.nr:
    print("NR:")
    print(f"  SA: {cap.nr.sa_supported}")
    print(f"  NSA: {cap.nr.nsa_supported}")
    print(f"  Bands: {[b.band for b in cap.nr.supported_bands]}")
    for b in cap.nr.supported_bands:
        print(f"    Band n{b.band}: mmwave={b.mmwave} dl_mimo={b.dl_mimo_layers}")
else:
    print("NR: NOT DETECTED")

print()
print("Summary:", cap.ue_capabilities_summary)

print()
expected_rat = "MULTI"
expected_lte_bands = [3, 7]
expected_nr_bands = [78]

ok = True
if cap.rat != expected_rat:
    print(f"FAIL: RAT={cap.rat}, expected {expected_rat}"); ok=False
else:
    print(f"PASS: RAT={cap.rat}")

if cap.lte:
    actual = sorted([b.band for b in cap.lte.supported_bands])
    if actual != expected_lte_bands:
        print(f"FAIL: LTE bands={actual}, expected {expected_lte_bands}"); ok=False
    else:
        print(f"PASS: LTE bands {actual}")
    mimo = cap.lte.supported_bands[0].dl_mimo_layers if cap.lte.supported_bands else None
    if mimo == 2:
        print(f"PASS: LTE MIMO = {mimo}")
    else:
        print(f"FAIL: LTE MIMO = {mimo}, expected 2"); ok=False
else:
    print("FAIL: LTE not detected"); ok=False

if cap.nr:
    actual_nr = sorted([b.band for b in cap.nr.supported_bands])
    if actual_nr != expected_nr_bands:
        print(f"FAIL: NR bands={actual_nr}, expected {expected_nr_bands}"); ok=False
    else:
        print(f"PASS: NR bands {actual_nr}")
    if cap.nr.sa_supported is True:
        print("PASS: NR SA=True")
    else:
        print(f"FAIL: NR SA={cap.nr.sa_supported}"); ok=False
    nr_mimo = cap.nr.supported_bands[0].dl_mimo_layers if cap.nr.supported_bands else None
    if nr_mimo == 2:
        print(f"PASS: NR MIMO = {nr_mimo}")
    else:
        print(f"FAIL: NR MIMO = {nr_mimo}, expected 2"); ok=False
else:
    print("FAIL: NR not detected"); ok=False

print()
print("=== OVERALL:", "ALL PASS" if ok else "SOME FAILURES", "===")
