import sqlite3
import os

DB_PATH = "database/toxins.db"

def create_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Proteins (
        accession_number TEXT PRIMARY KEY,
        name TEXT,
        full_name TEXT,
        organism TEXT,
        gene TEXT,
        description TEXT,
        sequence TEXT,
        length INTEGER
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ProteinShortNames (
        short_name_id INTEGER PRIMARY KEY AUTOINCREMENT,
        accession_number TEXT,
        short_name TEXT,
        FOREIGN KEY (accession_number) REFERENCES Proteins (accession_number)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ProteinAlternativeNames (
        alt_name_id INTEGER PRIMARY KEY AUTOINCREMENT,
        accession_number TEXT,
        alternative_name TEXT,
        FOREIGN KEY (accession_number) REFERENCES Proteins (accession_number)
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Peptides (
        peptide_id INTEGER PRIMARY KEY AUTOINCREMENT,
        accession_number TEXT,
        peptide_name TEXT,
        start_position INTEGER,
        end_position INTEGER,
        sequence TEXT,
        model_source TEXT,       -- 'PDB', 'AlphaFold', o NULL
        model_id TEXT,           -- ID del modelo PDB o AlphaFold
        model_link TEXT,
        pdb_file BLOB,           -- Contenido del archivo PDB
        is_full_structure INTEGER DEFAULT 0,  -- 1 si es estructura completa, 0 si es péptido cortado
        FOREIGN KEY (accession_number) REFERENCES Proteins(accession_number)
    );
    """)

    conn.commit()
    conn.close()
    print(f"[✓] Base de datos creada en: {DB_PATH}")

if __name__ == "__main__":
    create_database()
