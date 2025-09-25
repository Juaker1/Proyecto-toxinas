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
          AND LENGTH({SEQ_COL}) BETWEEN 31 AND 35
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

    # Muestra ejemplos
    for r in (p2_strict[:10] or p2[:10] or p1b[:10] or p1[:10]):
        print(r.id, r.name, r.seq)
