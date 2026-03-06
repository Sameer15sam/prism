# UE Capability Parser – Backend

## Overview
A deterministic, rule-based backend for parsing and comparing UE Capability Information logs
(4G LTE / 5G NR) based on 3GPP ASN.1 specifications.

**No ML. No datasets. No training pipeline.**  
All parsing is regex + index-based. All validation is spec-derived.

---

## Why No Dataset?

UE Capability logs are **specification-defined structures** governed by 3GPP standards:
- **LTE**: TS 36.306 (UE radio access capabilities) + TS 36.331 (RRC protocol)
- **NR**: TS 38.306 (NR UE radio access capabilities) + TS 38.331 (NR RRC)

The correctness of parsing is validated against **specification rules**, not statistical patterns.
Machine learning would be inappropriate here because:
1. There is no labeled dataset (UE logs are proprietary; no public corpus exists)
2. The parsing problem is deterministic – a decoded log has a single correct interpretation
3. Spec-based rules are auditable; ML predictions are not

---

## Project Structure

```
backend/
├── src/
│   ├── api/
│   │   └── fastapi_app.py     # FastAPI endpoints (POST /parse, POST /compare)
│   ├── parser/
│   │   ├── lexer.py           # Regex-based tokenizer
│   │   ├── context.py         # RAT/context state engine
│   │   ├── asn_parser.py      # Index-based ASN.1 structure builder
│   │   └── core.py            # Top-level parse pipeline
│   ├── model/
│   │   ├── enums.py           # 3GPP-aligned enumerations
│   │   └── capability_schema.py  # Pydantic capability models
│   ├── validator/
│   │   ├── rules.py           # Field-level 3GPP rule checks
│   │   └── consistency.py     # Cross-field consistency checks
│   ├── compare/
│   │   ├── diff.py            # DUT vs REF diff engine
│   │   └── explanation.py     # Rule-based explanation lookup
│   └── utils/
│       └── helpers.py         # Shared utilities
├── requirements.txt
└── README.md
```

---

## Running the Server

```bash
cd backend
pip install -r requirements.txt
uvicorn src.api.fastapi_app:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## API Endpoints

### `POST /parse`
Parse a single decoded UE Capability log.

```bash
curl -X POST http://localhost:8000/parse \
  -F "file=@../samples/ue_cap_lte_example.txt"
```

**Response:**
```json
{
  "status": "ok",
  "source_file": "ue_cap_lte_example.txt",
  "capability": { "rat": "LTE", "lte": { ... } },
  "validation_issues": []
}
```

### `POST /compare`
Compare DUT (device under test) vs REF (reference) capability logs.

```bash
curl -X POST http://localhost:8000/compare \
  -F "dut=@../samples/ue_cap_lte_example.txt" \
  -F "ref=@../samples/ue_cap_nr_example.txt"
```

**Response:**
```json
{
  "status": "ok",
  "summary": { "total_diffs": 5, "missing_in_dut": 2, ... },
  "diffs": [ { "field_path": "lte.band[3]", "status": "MISSING_IN_DUT", ... } ],
  "explanations": [ { "reason": "...", "spec_ref": "3GPP TS 36.306 §4.1" } ]
}
```

---

## Validation Approach

| Check Type | Examples | Spec Reference |
|---|---|---|
| Band range | LTE bands 1–256 | TS 36.331 §6.3.6 |
| MIMO layer values | 1, 2, 4, or 8 only | TS 36.306 §4.1 |
| UE Category | Valid categories 1–21 | TS 36.306 Table 4.1-1 |
| FR2 SCS constraint | FR2 requires SCS ≥ 60 kHz | TS 38.101-2 §5.3.2 |
| CA combo integrity | CA band ref must exist in band list | TS 36.306 §4.3a |
| EN-DC consistency | NSA requires LTE anchor | TS 37.340 §4.1 |

---

## Supported Log Formats
- Qualcomm-like decoded RRC text (QXDM/QCAT output style)
- MediaTek-like decoded ASN.1 dump
- Key: value pairs with nested `{` `}` blocks
