"""
Backend tests for the UE Capability Parser.

Run with:
    cd c:\\Users\\DELL\\OneDrive\\Desktop\\Prism1\\backend
    python -m pytest tests/ -v
"""

import os
import sys
import pytest

# Make sure the 'src' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.parser.core import parse_capability_log
from src.compare.diff import compare


# ──────────────────────────────────────────────
# Fixtures: load sample files
# ──────────────────────────────────────────────

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "samples")


def _load(fname: str) -> str:
    path = os.path.join(SAMPLES_DIR, fname)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ──────────────────────────────────────────────
# Test 1: LTE sample parsing
# ──────────────────────────────────────────────

class TestLTEParsing:
    def setup_method(self):
        text = _load("ue_cap_lte_example.txt")
        self.cap = parse_capability_log(text, source_file="ue_cap_lte_example.txt")

    def test_rat_detected_as_lte(self):
        assert self.cap.rat == "LTE", f"Expected LTE, got {self.cap.rat}"

    def test_lte_capability_present(self):
        assert self.cap.lte is not None

    def test_correct_band_count(self):
        assert len(self.cap.lte.supported_bands) == 6, (
            f"Expected 6 bands, got {len(self.cap.lte.supported_bands)}: "
            f"{[b.band for b in self.cap.lte.supported_bands]}"
        )

    def test_band_1_dl_mimo_4x4(self):
        b1 = next((b for b in self.cap.lte.supported_bands if b.band == 1), None)
        assert b1 is not None, "Band 1 not found"
        assert b1.dl_mimo_layers == 4, f"Band 1 DL MIMO: expected 4, got {b1.dl_mimo_layers}"

    def test_band_41_is_tdd(self):
        b41 = next((b for b in self.cap.lte.supported_bands if b.band == 41), None)
        assert b41 is not None, "Band 41 not found"
        assert b41.band_type == "TDD"

    def test_band_1_dl_256qam_supported(self):
        b1 = next((b for b in self.cap.lte.supported_bands if b.band == 1), None)
        assert b1 is not None
        assert b1.dl_256qam is True

    def test_ue_category_extracted(self):
        assert self.cap.lte.ue_category_dl is not None

    def test_ca_combos_extracted(self):
        assert len(self.cap.lte.ca_combos) == 3, (
            f"Expected 3 CA combos, got {len(self.cap.lte.ca_combos)}"
        )

    def test_summary_present(self):
        assert self.cap.ue_capabilities_summary is not None
        assert "lte" in self.cap.ue_capabilities_summary

    def test_nr_is_none(self):
        assert self.cap.nr is None


# ──────────────────────────────────────────────
# Test 2: NR (MULTI) sample parsing
# ──────────────────────────────────────────────

class TestNRParsing:
    def setup_method(self):
        text = _load("ue_cap_nr_example.txt")
        self.cap = parse_capability_log(text, source_file="ue_cap_nr_example.txt")

    def test_rat_detected_as_multi(self):
        assert self.cap.rat == "MULTI", f"Expected MULTI, got {self.cap.rat}"

    def test_lte_and_nr_present(self):
        assert self.cap.lte is not None
        assert self.cap.nr is not None

    def test_nr_band_count(self):
        assert len(self.cap.nr.supported_bands) == 4, (
            f"Expected 4 NR bands, got {len(self.cap.nr.supported_bands)}: "
            f"{[b.band for b in self.cap.nr.supported_bands]}"
        )

    def test_band_78_dl_mimo_4x4(self):
        b78 = next((b for b in self.cap.nr.supported_bands if b.band == 78), None)
        assert b78 is not None, "NR Band 78 not found"
        assert b78.dl_mimo_layers == 4

    def test_band_78_max_bw_100mhz(self):
        b78 = next((b for b in self.cap.nr.supported_bands if b.band == 78), None)
        assert b78 is not None
        assert b78.max_bw_dl == 100

    def test_band_257_is_mmwave(self):
        b257 = next((b for b in self.cap.nr.supported_bands if b.band == 257), None)
        assert b257 is not None, "NR Band 257 not found"
        assert b257.mmwave is True

    def test_sa_nsa_supported(self):
        assert self.cap.nr.sa_supported is True
        assert self.cap.nr.nsa_supported is True


# ──────────────────────────────────────────────
# Test 3: Compare DUT vs REF
# ──────────────────────────────────────────────

class TestDiffEngine:
    def setup_method(self):
        ref_text = _load("ue_cap_lte_example.txt")
        dut_text = _load("ue_cap_lte_dut.txt")
        self.ref = parse_capability_log(ref_text, source_file="ref")
        self.dut = parse_capability_log(dut_text, source_file="dut")
        self.result = compare(self.dut, self.ref)

    def test_diffs_detected(self):
        assert self.result.summary["total_diffs"] > 0

    def test_band_1_mimo_mismatch_detected(self):
        paths = [d.field_path for d in self.result.diffs]
        assert "lte.band[1].dl_mimo_layers" in paths, (
            f"Band 1 MIMO mismatch not found in diffs: {paths}"
        )

    def test_band_20_missing_detected(self):
        paths = [d.field_path for d in self.result.diffs]
        assert "lte.band[20]" in paths, (
            f"Missing band 20 not detected: {paths}"
        )

    def test_high_severity_exists(self):
        sevs = [d.severity for d in self.result.diffs]
        assert "HIGH" in sevs

    def test_ca_combo_count_mismatch(self):
        paths = [d.field_path for d in self.result.diffs]
        assert "lte.ca_combos.count" in paths


# ──────────────────────────────────────────────
# Test 4: Edge cases
# ──────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_input(self):
        cap = parse_capability_log("", source_file="empty")
        assert cap.rat == "UNKNOWN"
        assert cap.lte is None
        assert cap.nr is None

    def test_garbage_input(self):
        cap = parse_capability_log("this is not a log file at all!!!", source_file="garbage")
        # Should not crash; RAT should be UNKNOWN
        assert cap.rat in ("UNKNOWN", "LTE", "NR", "MULTI")

    def test_source_file_preserved(self):
        cap = parse_capability_log("", source_file="myfile.txt")
        assert cap.source_file == "myfile.txt"
