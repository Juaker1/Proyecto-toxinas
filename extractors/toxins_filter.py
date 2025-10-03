"""Motif filtering logic (NaSpTx-like) extracted from experimental test script.

Provides a pure function `search_motifs` returning scored motif hits
ready to be serialized by a Flask controller.
"""
from __future__ import annotations

import sqlite3, re
from collections import namedtuple
from typing import List, Dict, Any, Optional, Tuple

# Default configuration (can be overridden via function arguments)
DB_PATH = "database/toxins.db"
TABLE = "peptides"
SEQ_COL = "sequence"
NAME_FALLBACK = "peptide_name"

HYDRO = "FWYLIVMA"  # hydrophobic set for X positions
HYDRO_SET = set(HYDRO)

# Kyte-Doolittle scale (subset relevant to our hydrophobic set + others for robustness)
KYTE_DOOLITTLE = {
    "I": 4.5, "V": 4.2, "L": 3.8, "F": 2.8, "C": 2.5,
    "M": 1.9, "A": 1.8, "G": -0.4, "T": -0.7, "W": -0.9,
    "S": -0.8, "Y": -1.3, "P": -1.6, "H": -3.2, "E": -3.5,
    "Q": -3.5, "D": -3.5, "N": -3.5, "K": -3.9, "R": -4.5
}

PAT_WCKX3 = rf"WCK[{HYDRO}]"
PAT_S_BEFORE_WCKX3 = rf"S[A-Z]*WCK[{HYDRO}]"

Row = namedtuple("Row", "id name seq")


# ---- Metadata helpers ----
def pick_name_column(cur) -> str:
    cur.execute(f"PRAGMA table_info({TABLE})")
    cols = [c[1] for c in cur.fetchall()]
    lower = [c.lower() for c in cols]
    for cand in ("accession_number", "peptide_name", "model_source"):
        if cand in lower:
            return cols[lower.index(cand)]
    return NAME_FALLBACK


# ---- Core sequence predicates ----
def has_at_least_six_c(seq: str) -> bool:
    return seq.upper().count("C") >= 6


def link_c5_S_to_WCK_gap(seq: str, gap_min=3, gap_max=6):
    """Locate motif with constraints: S immediately after 5th C, WCKX3 at gap in [gap_min..gap_max].

    Returns tuple (ok, iC5, iS, iW, iK, iX3).
    Indices are 0-based.
    """
    s = seq.upper()
    cis = [i for i, a in enumerate(s) if a == "C"]
    if len(cis) < 5:
        return (False, None, None, None, None, None)
    iC5 = cis[4]
    iS = iC5 + 1
    if iS >= len(s) or s[iS] != "S":
        return (False, iC5, None, None, None, None)
    w_start = iS + gap_min
    w_end = min(iS + gap_max, len(s) - 3)  # ensure room for WCKX
    for iW in range(w_start, w_end + 1):
        if s[iW:iW + 3] == "WCK":
            iK = iW + 2
            iX3 = iK + 1
            if iX3 < len(s) and s[iX3] in HYDRO_SET:
                return (True, iC5, iS, iW, iK, iX3)
    return (False, iC5, iS, None, None, None)


def best_hydrophobic_pair_before_S(seq: str, iS: int) -> Tuple[bool, Optional[str], Optional[int], Optional[float]]:
    """Return (found, pair, start_index, score) for the best consecutive hydrophobic pair before S.

    Scoring: sum of Kyte-Doolittle values. If multiple pairs tie, first (leftmost) retained.
    """
    if iS is None or iS < 1:
        return (False, None, None, None)
    s = seq.upper()
    best_pair = None
    best_idx = None
    best_score = None
    for i in range(0, iS - 1):
        a1 = s[i]
        a2 = s[i + 1]
        if a1 in HYDRO_SET and a2 in HYDRO_SET:
            score = KYTE_DOOLITTLE.get(a1, 0.0) + KYTE_DOOLITTLE.get(a2, 0.0)
            if best_score is None or score > best_score:
                best_score = score
                best_pair = a1 + a2
                best_idx = i
    return (best_pair is not None, best_pair, best_idx, best_score)


# ---- Data access ----
def fetch_rows(db_path=DB_PATH) -> List[Row]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    name_col = pick_name_column(cur)
    cur.execute(
        f"SELECT peptide_id, {name_col} AS name, {SEQ_COL} AS seq FROM {TABLE} WHERE {SEQ_COL} IS NOT NULL"
    )
    rows = [Row(*r) for r in cur.fetchall()]
    conn.close()
    return rows


# ---- Public search function ----
def search_toxins(*, gap_min=3, gap_max=6, require_pair=False, db_path=DB_PATH) -> List[Dict[str, Any]]:
    """Execute motif search returning list of dict hits sorted by score desc.

    Scoring (current heuristic):
      +2 WCKX3 (implied)
      +2 gap within range
      +2 C>=6
      +2 S after 5th C
      +1 hydrophobic pair before S (optional, can also be enforced with require_pair)
    """
    rows = fetch_rows(db_path)
    rx_core = re.compile(PAT_WCKX3)
    rx_s_before = re.compile(PAT_S_BEFORE_WCKX3)
    # Step 1: require S...WCKX3 (broad, no distance constraint)
    candidates = [r for r in rows if rx_core.search(r.seq.upper()) and rx_s_before.search(r.seq.upper())]
    hits: List[Dict[str, Any]] = []
    for r in candidates:
        s = r.seq.upper()
        if not has_at_least_six_c(s):
            continue
        ok, iC5, iS, iW, iK, iX3 = link_c5_S_to_WCK_gap(s, gap_min, gap_max)
        if not ok:
            continue
        pair_flag, pair_str, pair_idx, pair_score = best_hydrophobic_pair_before_S(s, iS)
        if require_pair and not pair_flag:
            continue
        score = 2 + 2 + 2 + 2 + (1 if pair_flag else 0)
        hits.append({
            "peptide_id": r.id,
            "name": r.name,
            "sequence": r.seq,
            "score": score,
            "iC5": iC5,
            "iS": iS,
            "iW": iW,
            "iK": iK,
            "iX3": iX3,
            "X3": s[iX3] if iX3 is not None else None,
            # legacy boolean retained
            "has_hydrophobic_pair": pair_flag,
            # new detailed pair info
            "hydrophobic_pair": pair_str,
            "hydrophobic_pair_start": pair_idx,
            "hydrophobic_pair_score": pair_score,
            # explicit indices for highlighting
            "iHP1": pair_idx,
            "iHP2": (pair_idx + 1) if pair_idx is not None else None,
            "gap": (iW - iS) if (iW is not None and iS is not None) else None,
            "length": len(s)
        })
    hits.sort(key=lambda d: d["score"], reverse=True)
    return hits


__all__ = [
    "search_toxins",
    "fetch_rows",
    "has_at_least_six_c",
    "link_c5_S_to_WCK_gap",
    "has_hydrophobic_pair_before_S",
]
