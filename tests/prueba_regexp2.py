import sqlite3, re
from collections import namedtuple

DB_PATH = "database/toxins.db"      # <-- ajusta ruta
TABLE   = "peptides"
SEQ_COL = "sequence"
NAME_FALLBACK = "peptide_name"     # cambia si tu columna de nombre tiene otro nombre

# --- utilidades de metadatos ---
def pick_name_column(cur):
    cur.execute(f"PRAGMA table_info({TABLE})")
    cols = [c[1] for c in cur.fetchall()]
    lower = [c.lower() for c in cols]
    for cand in ("accession_number","peptide_name","model_source"):
        if cand in lower:
            return cols[lower.index(cand)]
    return NAME_FALLBACK

# --- registrar REGEXP en SQLite ---
def sqlite_regexp(pattern, text):
    if text is None:
        return 0
    return 1 if re.search(pattern, text) else 0

# --- hidrofóbicos para X ---
HYDRO = "FWYLIVMA"
HYDRO_SET = set(HYDRO)

# Paso 1a: Núcleo mínimo WCKX3
PAT_WCKX3 = rf"WCK[{HYDRO}]"

# Paso 1b (opcional): S...WCKX3 (sin fijar distancias)
PAT_S_BEFORE_WCKX3 = rf"S[A-Z]*WCK[{HYDRO}]"

# Paso 2a: contar C>=6
def has_at_least_six_c(seq: str) -> bool:
    return seq.count("C") >= 6

# Paso 2b (estricto NaSpTx1-like): S justo tras la 5ª C
def s_immediately_after_c5(seq: str) -> bool:
    cis = [i for i,aa in enumerate(seq) if aa == "C"]
    if len(cis) < 5:
        return False
    i5 = cis[4]
    return (i5 + 1 < len(seq)) and (seq[i5+1] == "S")

# ---------- (1) y (2): MISMA S (tras C5) + gap 3..6 hasta W de WCKX3 ----------
def link_c5_S_to_WCK_gap(seq: str, gap_min=3, gap_max=6):
    """
    Devuelve (ok, iC5, iS, iW, iK, iX3) donde:
      - ok = True si existe S justo tras C5 y luego aparece WCKX3
             con W a distancia [gap_min..gap_max] desde esa S.
    """
    s = seq.upper()
    # localizar C5 y S tras C5
    cis = [i for i,a in enumerate(s) if a == "C"]
    if len(cis) < 5:
        return (False, None, None, None, None, None)
    iC5 = cis[4]
    iS = iC5 + 1
    if iS >= len(s) or s[iS] != "S":
        return (False, iC5, None, None, None, None)

    # ventana donde debe caer el W (gap 3..6)
    w_start = iS + gap_min
    w_end   = min(iS + gap_max, len(s)-3)  # -3 para tener WCKX3 completo
    for iW in range(w_start, w_end + 1):
        if s[iW:iW+3] == "WCK":
            iK = iW + 2
            iX3 = iK + 1
            if iX3 < len(s) and s[iX3] in HYDRO_SET:
                return (True, iC5, iS, iW, iK, iX3)
    return (False, iC5, iS, None, None, None)

# ---------- (3): X1X2 hidrofóbicos ANTES de S (no bloquea, solo señal) ----------
def has_hydrophobic_pair_before_S(seq: str, iS: int) -> bool:
    """ True si existe al menos una pareja consecutiva de hidrofóbicos antes de iS. """
    s = seq.upper()
    for i in range(0, max(0, iS-1)):
        if s[i] in HYDRO_SET and s[i+1] in HYDRO_SET:
            return True
    return False

Row = namedtuple("Row", "id name seq")

def fetch_rows(db_path):
    conn = sqlite3.connect(db_path)
    conn.create_function("REGEXP", 2, sqlite_regexp)
    cur = conn.cursor()
    name_col = pick_name_column(cur)
    cur.execute(f"""
        SELECT peptide_id, {name_col} AS name, {SEQ_COL} AS seq
        FROM {TABLE}
        WHERE {SEQ_COL} IS NOT NULL
    """)
    rows = [Row(*r) for r in cur.fetchall()]
    conn.close()
    return rows

def pass1_recall(rows, require_S_before=False):
    """ Paso 1: recall alto. """
    rx_core = re.compile(PAT_WCKX3)
    rx_s_before = re.compile(PAT_S_BEFORE_WCKX3)
    out = []
    for r in rows:
        s = r.seq.upper()
        if not rx_core.search(s):
            continue
        if require_S_before and not rx_s_before.search(s):
            continue
        out.append(r)
    return out

def pass2_refine(rows, need_6C=True, need_S_after_C5=False):
    """ Paso 2: filtros estructurales. """
    out = []
    for r in rows:
        s = r.seq.upper()
        if need_6C and not has_at_least_six_c(s):
            continue
        if need_S_after_C5 and not s_immediately_after_c5(s):
            continue
        out.append(r)
    return out

# -------- NUEVO: paso 2 'estricto+' enlazando S(C5) -> gap 3..6 -> WCKX3 ----------
def pass2_linked_gap(rows, gap_min=3, gap_max=6):
    """
    Aplica: C>=6, S tras C5, y enlaza esa S con WCKX3 a gap [3..6].
    Devuelve lista de tuplas (Row, meta) para poder escorar luego.
    """
    kept = []
    for r in rows:
        s = r.seq.upper()
        if not has_at_least_six_c(s):
            continue
        ok, iC5, iS, iW, iK, iX3 = link_c5_S_to_WCK_gap(s, gap_min, gap_max)
        if not ok:
            continue
        meta = {"iC5": iC5, "iS": iS, "iW": iW, "iK": iK, "iX3": iX3,
                "X3": s[iX3] if iX3 is not None else None,
                "has_X1X2_before_S": has_hydrophobic_pair_before_S(s, iS)}
        kept.append((r, meta))
    return kept

if __name__ == "__main__":
    rows = fetch_rows(DB_PATH)

    # --- Paso 1: captura amplia ---
    p1 = pass1_recall(rows, require_S_before=False)   # solo WCKX3
    print(f"[Paso 1a] WCKX3 -> {len(p1)} candidatos")

    p1b = pass1_recall(rows, require_S_before=True)   # S...WCKX3
    print(f"[Paso 1b] S...WCKX3 -> {len(p1b)} candidatos")

    # --- Paso 2: refinar (aplica sobre p1b o p1, según prefieras) ---
    p2 = pass2_refine(p1b, need_6C=True, need_S_after_C5=False)
    print(f"[Paso 2] + (C>=6) -> {len(p2)} candidatos")

    p2_strict = pass2_refine(p1b, need_6C=True, need_S_after_C5=True)
    print(f"[Paso 2-estricto] + S tras 5ª C -> {len(p2_strict)} candidatos")

    # -------- NUEVO: Paso 2-estricto+ enlazando con gap 3..6 ----------
    linked = pass2_linked_gap(p1b, gap_min=3, gap_max=6)
    print(f"[Paso 2-estricto+] S(C5) —gap 3..6→ WCKX3 -> {len(linked)} candidatos")

    # Muestra ejemplos (se mantiene tu lógica de muestra)
    for r in (p2_strict[:10] or p2[:10] or p1b[:10] or p1[:10]):
        print(r.id, r.name, r.seq)

    # -------- (6) Scoring al final (no interrumpe tus prints) ----------
    # Pequeño ranking para priorizar: base sobre 'linked' (que ya cumple lo fuerte)
    # Puntos:
    # +2 si tiene WCKX3 (trivial en linked)
    # +2 si gap S→W en [3..6] (trivial en linked)
    # +2 si C>=6 (trivial en linked)
    # +2 si S tras C5 (trivial en linked)
    # +1 si hay pareja hidrofóbica X1X2 antes de S (señal, no bloqueo)
    scored = []
    for r, meta in linked:
        score = 0
        score += 2  # WCKX3
        score += 2  # gap 3..6
        score += 2  # C>=6
        score += 2  # S tras C5
        if meta.get("has_X1X2_before_S"):
            score += 1
        scored.append((score, r, meta))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        print("\n[Ranking] Top 10 por score (no afecta los prints previos):")
        for sc, r, meta in scored[:10]:
            print(f"score={sc}  id={r.id}  name={r.name}  X3={meta['X3']}  "
                  f"pos(S)={meta['iS']}  pos(W)={meta['iW']}  X1X2_prev={meta['has_X1X2_before_S']}")
