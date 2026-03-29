"""
Sequential extractor for UE Capability Parser.
Extracts band combinations in index order using brace counting.
"""

import re
from typing import Dict, List, Any, Optional


class SequentialExtractor:

    def __init__(self, content: str, rat_type: str):
        self.content = content
        self.rat_type = rat_type

    def extract_all(self) -> List[Dict[str, Any]]:
        section = self._find_band_combination_section()
        if not section:
            raise ValueError("supportedBandCombinationList not found in file")
        blocks = self._split_into_blocks(section)
        combinations = []
        for i, block in enumerate(blocks):
            combo = self._parse_combination_block(block, i)
            combinations.append(combo)
        return combinations

    def _find_band_combination_section(self) -> Optional[str]:
        marker = "supportedBandCombinationList"
        idx = self.content.find(marker)
        if idx == -1:
            return None
        brace_start = self.content.find("{", idx)
        if brace_start == -1:
            return None
        depth = 0
        i = brace_start
        while i < len(self.content):
            if self.content[i] == "{":
                depth += 1
            elif self.content[i] == "}":
                depth -= 1
                if depth == 0:
                    return self.content[brace_start + 1 : i]
            i += 1
        return None

    def _split_into_blocks(self, section: str) -> List[str]:
        blocks = []
        depth = 0
        start = -1
        for i, char in enumerate(section):
            if char == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0 and start != -1:
                    blocks.append(section[start + 1 : i])
                    start = -1
        return blocks

    def _parse_combination_block(self, block: str, index: int) -> Dict[str, Any]:
        return {
            "combination_index": index,
            "bands": self._extract_bands(block),
            "feature_set_combination": self._extract_feature_set(block),
            "mrdc_parameters": self._extract_mrdc_params(block),
            "optional_fields": self._extract_optional_fields(block)
        }

    def _extract_bands(self, block: str) -> List[Dict[str, Any]]:
        bands = []
        bandlist_start = block.find("bandList")
        if bandlist_start == -1:
            return bands
        brace_start = block.find("{", bandlist_start)
        if brace_start == -1:
            return bands
        depth = 0
        i = brace_start
        end = brace_start
        while i < len(block):
            if block[i] == "{":
                depth += 1
            elif block[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
            i += 1
        bandlist_content = block[brace_start + 1 : end]

        # Extract eutra entries
        for eutra_block in self._extract_rat_blocks(bandlist_content, "eutra"):
            band = {}
            band["rat"] = "EUTRA"
            m = re.search(r'bandEUTRA\s+(\d+)', eutra_block)
            if m:
                band["band"] = int(m.group(1))
            m = re.search(r'ca-BandwidthClassDL-EUTRA\s+(\S+)', eutra_block)
            if m:
                band["ca_bw_class_dl"] = m.group(1).rstrip(',')
            m = re.search(r'ca-BandwidthClassUL-EUTRA\s+(\S+)', eutra_block)
            if m:
                band["ca_bw_class_ul"] = m.group(1).rstrip(',')
            if "band" in band:
                bands.append(band)

        # Extract nr entries
        for nr_block in self._extract_rat_blocks(bandlist_content, "nr"):
            band = {}
            band["rat"] = "NR"
            m = re.search(r'bandNR\s+(\d+)', nr_block)
            if m:
                band["band"] = int(m.group(1))
            m = re.search(r'ca-BandwidthClassDL-NR\s+(\S+)', nr_block)
            if m:
                band["ca_bw_class_dl"] = m.group(1).rstrip(',')
            m = re.search(r'ca-BandwidthClassUL-NR\s+(\S+)', nr_block)
            if m:
                band["ca_bw_class_ul"] = m.group(1).rstrip(',')
            if "band" in band:
                bands.append(band)

        return bands

    def _extract_rat_blocks(self, bandlist_content: str, rat: str) -> List[str]:
        blocks = []
        search_from = 0
        pattern = rat + r'\s*:'
        for m in re.finditer(pattern, bandlist_content):
            brace_start = bandlist_content.find("{", m.end())
            if brace_start == -1:
                continue
            depth = 0
            i = brace_start
            while i < len(bandlist_content):
                if bandlist_content[i] == "{":
                    depth += 1
                elif bandlist_content[i] == "}":
                    depth -= 1
                    if depth == 0:
                        blocks.append(bandlist_content[brace_start + 1 : i])
                        break
                i += 1
        return blocks

    def _extract_feature_set(self, block: str) -> Optional[int]:
        m = re.search(r'featureSetCombination\s+(\d+)', block)
        return int(m.group(1)) if m else None

    def _extract_mrdc_params(self, block: str) -> Dict[str, str]:
        params = {}
        mrdc_start = block.find("mrdc-Parameters")
        if mrdc_start == -1:
            return params
        brace_start = block.find("{", mrdc_start)
        if brace_start == -1:
            return params
        depth = 0
        i = brace_start
        while i < len(block):
            if block[i] == "{":
                depth += 1
            elif block[i] == "}":
                depth -= 1
                if depth == 0:
                    mrdc_content = block[brace_start + 1 : i]
                    break
            i += 1
        for field in ["dynamicPowerSharingENDC",
                      "simultaneousRxTxInterBandENDC",
                      "intraBandENDC-Support"]:
            m = re.search(rf'{field}\s+(\S+)', mrdc_content)
            if m:
                params[field] = m.group(1).rstrip(',')
        return params

    def _extract_optional_fields(self, block: str) -> Dict[str, str]:
        optional = {}
        for field in ["powerClass-v1530", "supportedBandwidthCombinationSet"]:
            m = re.search(rf'{field}\s+(\S+)', block)
            if m:
                optional[field] = m.group(1).rstrip(',')
        return optional


def sequential_extract(content: str, rat_type: str) -> List[Dict[str, Any]]:
    extractor = SequentialExtractor(content, rat_type)
    return extractor.extract_all()
