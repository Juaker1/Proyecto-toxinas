import sqlite3

DB_PATH = "database/toxins.db" 

# Datos extraídos de la imagen del paper
peptides_data = [
    {
        "accession_number": "P83303", "peptide_code": "μ-TRTX-Hh2a", "sequence": "ECLEIFKACNPSNDQCCKSSKLVCSRKTRWCKYQI", "pharmacophore_match": "IF–S–WCKY", "residue_count": 7, "ic50": 17.0, "unit": "nM", "pdb_download_link": "https://files.rcsb.org/download/1MB6.pdb"
    },
    {
        "accession_number": None, "peptide_code": "μ-TRTX-Hh2a_E1A", "sequence": "ACLEIFKACNPSNDQCCKSSKLVCSRKTRWCKYQI", "pharmacophore_match": "IF–S–WCKY", "residue_count": 7, "ic50": 6.0, "unit": "nM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "μ-TRTX-Hh2a_E4A", "sequence": "ECLAIFKACNPSNDQCCKSSKLVCSRKTRWCKYQI", "pharmacophore_match": "IF–S–WCKY", "residue_count": 7, "ic50": 26.0, "unit": "nM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "μ-TRTX-Hh2a_Y33W", "sequence": "ECLEIFKACNPSNDQCCKSSKLVCSRKTRWCKWQI", "pharmacophore_match": "IF–S–WCKW", "residue_count": 7, "ic50": 1.4, "unit": "nM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "μ-TRTX-Hh2a_E1A_E4A_Y33W", "sequence": "ACLAIFKACNPSNDQCCKSSKLVCSRKTRWCKWQI", "pharmacophore_match": "IF–S–WCKW", "residue_count": 7, "ic50": 0.6, "unit": "nM", "pdb_download_link": None
    },
    {
        "accession_number": "P84507", "peptide_code": "β-TRTX-Cm1a", "sequence": "DCLGWFKSCDPKNDKCCKNYTCSRRDRWCKYDL", "pharmacophore_match": "WF–S–WCKY", "residue_count": 7, "ic50": 5.1, "unit": "μM", "pdb_download_link": "https://files.rcsb.org/download/5EPM.pdb"
    },
    {
        "accession_number": "P0DL84", "peptide_code": "β-TRTX-Cd1a", "sequence": "DCLGWFKSCDPKNDKCCKNYSCSRRDRWCKYDL", "pharmacophore_match": "WF–S–WCKY", "residue_count": 7, "ic50": 2.2, "unit": "nM", "pdb_download_link": "https://alphafold.ebi.ac.uk/files/AF-P0DL84-F1-model_v4.pdb"
    },
    {
        "accession_number": "P84508", "peptide_code": "β-TRTX-Cm1b", "sequence": "DCLGWFKSCDPKNDKCCKNYTCSRRDRWCKYYL", "pharmacophore_match": "WF–S–WCKY", "residue_count": 7, "ic50": 0.2, "unit": "μM", "pdb_download_link": "https://files.rcsb.org/download/6BTV.pdb"
    },
    {
        "accession_number": "D2Y1X8", "peptide_code": "μ-TRTX-Hhn2b", "sequence": "ECKGFGKSCVPGKNECCSGYACNSRDKWCKVLL", "pharmacophore_match": "FG–S–WCKV", "residue_count": 5, "ic50": 10.0, "unit": "μM", "pdb_download_link": "https://alphafold.ebi.ac.uk/files/AF-D2Y1X8-F1-model_v4.pdb"
    },
    {
        "accession_number": None, "peptide_code": "μ-TRTX-Hhn2b_G6W", "sequence": "ECKGFWKSCVPGKNECCSGYACNSRDKWCKVLL", "pharmacophore_match": "FW–N–WCKY", "residue_count": 6, "ic50": 2.7, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "μ-TRTX-Hhn2b_N23S", "sequence": "ECKGFGKSCVPGKNECCSGYACSSRDKWCKVLL", "pharmacophore_match": "FG–S–WCKV", "residue_count": 6, "ic50": 4.0, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "μ-TRTX-Hhn2b_G6W_N23S", "sequence": "ECKGFWKSCVPGKNECCSGYACSSRDKWCKVLL", "pharmacophore_match": "FW–S–WCKY", "residue_count": 7, "ic50": 0.4, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": "P0DL72", "peptide_code": "ω-TRTX-Gr2a", "sequence": "DCLGFMRKCIPDNDKCCRPNLVCSRTHKWCKYVF", "pharmacophore_match": "FM–S–WCKY", "residue_count": 7, "ic50": 0.1, "unit": "μM", "pdb_download_link": "https://files.rcsb.org/download/6MK5.pdb"
    },
    {
        "accession_number": None, "peptide_code": "ω-TRTX-Gr2a_F5A", "sequence": "DCLGAMRKCIPDNDKCCRPNLVCSRTHKWCKYVF", "pharmacophore_match": "AM–S–WCKY", "residue_count": 6, "ic50": 0.6, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "ω-TRTX-Gr2a_M6A", "sequence": "DCLGFARKCIPDNDKCCRPNLVCSRTHKWCKYVF", "pharmacophore_match": "FA–S–WCKY", "residue_count": 6, "ic50": 0.4, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "ω-TRTX-Gr2a_S24A", "sequence": "DCLGFMRKCIPDNDKCCRPNLVCARTHKWCKYVF", "pharmacophore_match": "FM–A–WCKY", "residue_count": 6, "ic50": 0.5, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "ω-TRTX-Gr2a_W29A", "sequence": "DCLGFMRKCIPDNDKCCRPNLVCSRTHKACKYVF", "pharmacophore_match": "FM–S–WCKY", "residue_count": 6, "ic50": 5.0, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "ω-TRTX-Gr2a_K31A", "sequence": "DCLGFMRKCIPDNDKCCRPNLVCSRTHKWCAYVF", "pharmacophore_match": "FM–S–WCKY", "residue_count": 6, "ic50": 5.0, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "ω-TRTX-Gr2a_Y32A", "sequence": "DCLGFMRKCIPDNDKCCRPNLVCSRTHKWCKAVF", "pharmacophore_match": "FM–S–WCKY", "residue_count": 6, "ic50": 0.8, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "ω-TRTX-Gr2a_G4W", "sequence": "DCLWFMRKCIPDNDKCCRPNLVCSRTHKWCKYVF", "pharmacophore_match": "FM–S–WCKY", "residue_count": 7, "ic50": 0.3, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "ω-TRTX-Gr2a_P11W", "sequence": "DCLGFMRKCIWDNDKCCRPNLVCSRTHKWCKYVF", "pharmacophore_match": "FM–S–WCKY", "residue_count": 7, "ic50": 0.1, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": None, "peptide_code": "ω-TRTX-Gr2a_K28A", "sequence": "DCLGFMRKCIPDNDKCCRPNLVCSRTHAWCKYVF", "pharmacophore_match": "FM–S–WCKY", "residue_count": 7, "ic50": 0.5, "unit": "μM", "pdb_download_link": None
    },
    {
        "accession_number": "P0CH54", "peptide_code": "μ-TRTX-Cg4a", "sequence": "SCKVPFNECKYGADECCKGYVCSKRDGWCKYHIN", "pharmacophore_match": "PF–S–WCKY", "residue_count": 6, "ic50": 9.2, "unit": "μM", "pdb_download_link": "https://files.rcsb.org/download/8FD4.pdb"
    }
]

def insert_peptides():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for p in peptides_data:
        cursor.execute("""
        INSERT INTO Nav1_7_InhibitorPeptides (
            accession_number,
            peptide_code,
            sequence,
            pharmacophore_match,
            pharmacophore_residue_count,
            ic50_value,
            ic50_unit,
            pdb_download_link
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["accession_number"],
            p["peptide_code"],
            p["sequence"],
            p["pharmacophore_match"],
            p["residue_count"],
            p["ic50"],
            p["unit"],
            p["pdb_download_link"]
        ))
    conn.commit()
    conn.close()
    print(f"[✓] Insertados {len(peptides_data)} péptidos en la tabla.")

'''
if __name__ == "__main__":
    insert_peptides()
'''