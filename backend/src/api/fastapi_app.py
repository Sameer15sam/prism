"""
FastAPI Application – UE Capability Parser API

Endpoints:
  POST /parse   – parse a single UE capability log file
  POST /compare – compare DUT vs REF capability logs

Design:
  - Stateless (no database)
  - No authentication
  - All logic is deterministic
  - CORS enabled for local development
"""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict

from ..parser.core import parse_capability_log
from ..validator.rules import validate
from ..validator.consistency import check_consistency
from ..compare.diff import compare
from ..compare.explanation import attach_explanations
from ..compare.ref_gen import generate_reference
from ..model.capability_schema import NormalizedCapability, CompareResult


# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────

app = FastAPI(
    title="UE Capability Parser",
    description=(
        "Deterministic parsing and comparison of 4G LTE / 5G NR UE Capability "
        "Information logs based on 3GPP ASN.1 specifications. "
        "No ML. No datasets. Rule-based only."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────

class ParseResponse(BaseModel):
    status: str
    source_file: str
    capability: Dict[str, Any]
    validation_issues: list


class CompareResponse(BaseModel):
    status: str
    dut_file: str
    ref_file: str
    summary: Dict[str, int]
    diffs: list
    explanations: list


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "ue-capability-parser"}


@app.post("/parse", response_model=ParseResponse, tags=["Parse"])
async def parse_log(file: UploadFile = File(...)) -> ParseResponse:
    """
    Parse a single decoded RRC UE Capability log.

    - **file**: Text file containing the decoded RRC log (Qualcomm/MediaTek format)

    Returns a normalized capability JSON and any 3GPP rule violations found.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    try:
        content = await file.read()
        text = content.decode("utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read file: {exc}")

    cap: NormalizedCapability = parse_capability_log(text, source_file=file.filename)

    # Validate
    issues = validate(cap)
    issues += check_consistency(cap)
    cap.validation_issues = issues

    return ParseResponse(
        status="ok",
        source_file=file.filename,
        capability=cap.model_dump(exclude={"validation_issues", "raw_fields"}),
        validation_issues=[i.model_dump() for i in issues],
    )


@app.post("/compare", response_model=CompareResponse, tags=["Compare"])
async def compare_logs(
    dut: UploadFile = File(...),
    ref: UploadFile = File(...),
) -> CompareResponse:
    """
    Compare DUT vs REF UE Capability logs.

    - **dut**: Device Under Test log file
    - **ref**: Reference device log file

    Returns structured diff entries classified as:
    MISSING_IN_DUT | EXTRA_IN_DUT | VALUE_MISMATCH
    along with human-readable 3GPP-spec-referenced explanations.
    """
    try:
        dut_text = (await dut.read()).decode("utf-8", errors="replace")
        ref_text = (await ref.read()).decode("utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read files: {exc}")

    dut_cap = parse_capability_log(dut_text, source_file=dut.filename or "dut")
    ref_cap = parse_capability_log(ref_text, source_file=ref.filename or "ref")

    result: CompareResult = compare(dut_cap, ref_cap)
    result = attach_explanations(result)

    return CompareResponse(
        status="ok",
        dut_file=dut_cap.source_file,
        ref_file=ref_cap.source_file,
        summary=result.summary,
        diffs=[d.model_dump() for d in result.diffs],
        explanations=[e.model_dump() for e in result.explanations],
    )


@app.post("/reference", response_model=ParseResponse, tags=["Reference"])
async def create_reference(file: UploadFile = File(...)) -> ParseResponse:
    """
    Parse a UE capability log and generate a sanitized reference JSON.
    Removes None values and produces a cleaner normalized output
    for diffing or saving as a strict golden configuration.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    try:
        content = await file.read()
        text = content.decode("utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read file: {exc}")

    cap: NormalizedCapability = parse_capability_log(text, source_file=file.filename)
    ref_cap = generate_reference(cap)

    # Validate the reference build
    issues = validate(ref_cap)
    issues += check_consistency(ref_cap)
    ref_cap.validation_issues = issues

    return ParseResponse(
        status="ok",
        source_file=ref_cap.source_file,
        capability=ref_cap.model_dump(exclude={"validation_issues", "raw_fields"}),
        validation_issues=[i.model_dump() for i in issues],
    )

