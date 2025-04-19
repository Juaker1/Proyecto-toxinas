import aiohttp
import asyncio
import sqlite3
import os
import json
import re
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests
import ssl
import certifi

DB_PATH = "database/toxins.db"


# Clase auxiliar para manejar conexiones SQLite de forma segura.
# Utiliza el protocolo de contexto (`with`) para abrir y cerrar automáticamente la conexión.
# Proporciona acceso al cursor de la base de datos y garantiza el commit/cierre correcto al salir del contexto.
class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        return self.conn.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.commit()
            self.conn.close()

# Clase principal que encapsula todo el flujo de trabajo para:
# 1. Buscar proteínas en UniProt según una query (usando su API REST).
# 2. Descargar los datos XML individuales de cada accession number.
# 3. Parsear los datos relevantes de cada proteína (nombres, secuencia, estructura, etc.).
# 4. Guardar esta información tanto en un archivo XML bien estructurado como en una base de datos SQLite.
# También maneja reintentos automáticos ante errores HTTP y formatea archivos de salida con nombres seguros.
class UniProtPipeline:

    BASE_URL = "https://rest.uniprot.org/uniprotkb/search"

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.session = self.create_retry_session()

    def create_retry_session(self, retries=3, backoff_factor=0.5, status_forcelist=(500, 502, 504, 429)):
        # Crea una sesión HTTP con política de reintentos.
        # Útil para manejar errores temporales como 429 (Too Many Requests) o fallos de red.
        # La sesión se reutiliza en todas las peticiones para mejorar la estabilidad.

        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def sanitize_filename(self, text):
        # Convierte una cadena de texto en un nombre de archivo seguro.
        # Reemplaza caracteres no permitidos por guiones bajos.
        # Se usa para nombrar archivos JSON y XML basados en la query original.
        return re.sub(r"[^\w\-_.]", "_", text.strip().lower())

    def fetch_accessions(self, query, size=500):
        # Realiza una búsqueda en la API REST de UniProt usando una query.
        # Recupera los `accession numbers` (identificadores únicos de proteínas).
        # Guarda el resultado en un archivo JSON y retorna la lista y un prefijo limpio basado en la query.

        print(f"[•] Buscando proteínas con query: '{query}'")
        accession_numbers = set()
        params = {
            "query": query,
            "format": "json",
            "size": size,
            "fields": "accession"
        }

        while True:
            response = self.session.get(self.BASE_URL, params=params)
            if response.status_code == 200:
                data = response.json()
                entries = data.get("results", [])
                for entry in entries:
                    accession = entry.get("primaryAccession")
                    if accession:
                        accession_numbers.add(accession)
                print(f"  ↳ Recuperadas: {len(entries)} (Total: {len(accession_numbers)})")

                link = response.links.get("next")
                if link:
                    self.BASE_URL = link["url"]
                    params = {}
                else:
                    break
            else:
                print(f"[!] Error en la respuesta: {response.status_code}")
                break

        if not accession_numbers:
            print("[!] No se encontraron accession numbers.")
            return None, None

        safe_query = self.sanitize_filename(query)
        json_file = f"data/processed/{safe_query}_accessions.json"
        os.makedirs(os.path.dirname(json_file), exist_ok=True)
        with open(json_file, "w") as f:
            json.dump(list(accession_numbers), f)

        print(f"[✓] Accession numbers guardados en: {json_file}")
        return list(accession_numbers), safe_query

    @staticmethod
    def parse_protein(xml_content, accession):
        # Parsea el XML de una entrada de UniProt y extrae la información relevante.
        # Devuelve un diccionario con los datos de:
        # nombre, organismo, gen, descripción funcional, secuencia, longitud, nombres alternativos,
        # así como features tipo `peptide` o `chain`, y estructuras `PDB` y `AlphaFoldDB`.

        root = ET.fromstring(xml_content)
        ns = {'up': 'http://uniprot.org/uniprot'}

        def get_text(xpath):
            el = root.find(xpath, ns)
            return el.text.strip() if el is not None else None

        return {
            "accession_number": accession,
            "name": get_text("up:entry/up:name"),
            "full_name": get_text("up:entry/up:protein/up:recommendedName/up:fullName"),
            "organism": get_text("up:entry/up:organism/up:name[@type='scientific']"),
            "gene": get_text("up:entry/up:gene/up:name[@type='primary']"),
            "description": get_text("up:entry/up:comment[@type='function']/up:text"),
            "sequence": get_text("up:entry/up:sequence"),
            "length": root.find("up:entry/up:sequence", ns).attrib.get("length") if root.find("up:entry/up:sequence", ns) is not None else None,
            "short_names": [e.text for e in root.findall("up:entry/up:protein/up:alternativeName/up:shortName", ns)],
            "alternative_names": [e.text for e in root.findall("up:entry/up:protein/up:alternativeName/up:fullName", ns)],
            "features": root.findall("up:entry/up:feature[@type='peptide']", ns) + root.findall("up:entry/up:feature[@type='chain']", ns),
            "structures": root.findall("up:entry/up:dbReference[@type='PDB']", ns) + root.findall("up:entry/up:dbReference[@type='AlphaFoldDB']", ns)
        }

    async def fetch_all_async(self, accessions, output_xml_path):
        # Lanza múltiples peticiones concurrentes para descargar los datos XML de cada `accession`.
        # Usa `asyncio` y `aiohttp` para paralelizar la descarga.
        # Después del procesamiento, guarda los resultados en XML y los inserta en la base de datos.

        sem = asyncio.Semaphore(20)  # Adjusted semaphore limit

        async def fetch_one(session, acc):
            url = f"https://rest.uniprot.org/uniprotkb/{acc}.xml"
            last_status = None
            last_exception = None
            async with sem:
                for attempt in range(3):  # Keep 3 attempts
                    try:
                        # Increased timeout for the request
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                            last_status = resp.status
                            if resp.status == 200:
                                xml_data = await resp.read()
                                if not xml_data or not xml_data.strip():
                                    # Keep this specific error message
                                    print(f"[!] Contenido XML vacío o inválido para {acc}")
                                    return None
                                try:
                                    return self.parse_protein(xml_data, acc)
                                except ET.ParseError as parse_error:
                                    # Keep this specific error message
                                    print(f"[!] Error al parsear XML para {acc}: {parse_error}")
                                    return None
                            elif resp.status == 404:
                                # Keep this specific error message
                                print(f"[!] Accession {acc} no encontrado (404).")
                                return None  # No need to retry 404
                            elif resp.status in {429, 500, 502, 503, 504}:
                                # Removed verbose retry message
                                await asyncio.sleep(2 * (attempt + 1))
                            else:
                                # Removed verbose retry message for unexpected status
                                await asyncio.sleep(2 * (attempt + 1))
                    # Keep exception handling but remove verbose logging
                    except aiohttp.ClientError as client_error:
                        last_exception = client_error
                        await asyncio.sleep(2 * (attempt + 1))
                    except asyncio.TimeoutError as timeout_error:
                        last_exception = timeout_error
                        await asyncio.sleep(2 * (attempt + 1))
                    except Exception as e:
                        last_exception = e
                        await asyncio.sleep(2 * (attempt + 1))

                # Simplified final failure message
                print(f"[!] Fallo final al recuperar {acc}.")
                return None

        # Create an SSL context using certifi's CA bundle
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        # Pass the context to the session
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            tasks = [fetch_one(session, acc) for acc in accessions]
            results = await asyncio.gather(*tasks)

        proteins = [r for r in results if r is not None]
        print(f"[✓] Proteínas recuperadas exitosamente: {len(proteins)}")

        if proteins:  # Only save/insert if proteins were actually fetched
            self.save_to_xml(proteins, output_xml_path)
            self.insert_into_database(proteins)
        else:
            print("[!] No se recuperaron proteínas válidas para guardar.")

    def save_to_xml(self, proteins, path):
        # Guarda toda la información de las proteínas en un archivo XML legible.
        # Incluye nombre, secuencia, nombres alternativos, péptidos (`feature`) y estructuras (`dbReference`).
        # Se asegura de limpiar cualquier atributo `None` antes de serializar.
        # Usa `minidom` para formatear el XML con sangrías y guardarlo como archivo de texto.

        root = ET.Element("proteins")
        for p in proteins:
            prot = ET.SubElement(root, "protein", accession=p["accession_number"])
            ET.SubElement(prot, "name").text = p["name"]
            ET.SubElement(prot, "fullName").text = p["full_name"]
            ET.SubElement(prot, "organism").text = p["organism"]
            ET.SubElement(prot, "gene").text = p["gene"]
            ET.SubElement(prot, "description").text = p["description"]
            ET.SubElement(prot, "sequence").text = p["sequence"]
            ET.SubElement(prot, "length").text = str(p["length"]) if p["length"] else None

            sn_elem = ET.SubElement(prot, "shortNames")
            for short in p["short_names"]:
                ET.SubElement(sn_elem, "shortName").text = short

            alt_elem = ET.SubElement(prot, "alternativeNames")
            for alt in p["alternative_names"]:
                ET.SubElement(alt_elem, "alternativeName").text = alt

            # Features: guardar peptidos si hay, si no, cadenas
            peptides_elem = ET.SubElement(prot, "peptides")
            peptide_feats = [f for f in p.get("features", []) if f.attrib.get("type") == "peptide"]
            chain_feats = [f for f in p.get("features", []) if f.attrib.get("type") == "chain"]
            selected_features = peptide_feats if peptide_feats else chain_feats

            for f in selected_features:
                f_elem = ET.SubElement(peptides_elem, "feature", type=f.attrib.get("type"))
                if "description" in f.attrib:
                    f_elem.set("description", f.attrib["description"])
                loc = f.find("{http://uniprot.org/uniprot}location")
                if loc is not None:
                    begin = loc.find("{http://uniprot.org/uniprot}begin")
                    end = loc.find("{http://uniprot.org/uniprot}end")
                    pos = loc.find("{http://uniprot.org/uniprot}position")
                    if begin is not None:
                        f_elem.set("begin", begin.attrib.get("position"))
                    if end is not None:
                        f_elem.set("end", end.attrib.get("position"))
                    if pos is not None:
                        f_elem.set("position", pos.attrib.get("position"))

            structs_elem = ET.SubElement(prot, "structures")
            for s in p.get("structures", []):
                s_type = s.attrib.get("type") or ""
                s_id = s.attrib.get("id") or ""
                if s_type and s_id:
                    s_elem = ET.SubElement(structs_elem, "structure", type=s_type, id=s_id)
                    for prop in s.findall("{http://uniprot.org/uniprot}property"):
                        prop_type = prop.attrib.get("type")
                        prop_value = prop.attrib.get("value")
                        if prop_type and prop_value:
                            s_elem.set(prop_type, prop_value)

        for elem in root.iter():
            for k in list(elem.attrib):
                if elem.attrib[k] is None:
                    elem.attrib[k] = "algo none" 

        for protein in list(root.findall("protein")):
            if any("algo none" in (child.text or "") or any("algo none" in (v or "") for v in child.attrib.values()) for child in protein.iter()):
                root.remove(protein)

        xml_str = ET.tostring(root, encoding="utf-8")
        parsed = minidom.parseString(xml_str)
        pretty_xml = parsed.toprettyxml(indent="  ")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(pretty_xml)

        print(f"[✓] XML guardado en formato legible en: {path}")

    def insert_into_database(self, proteins):
        # Inserta los datos extraídos de cada proteína en la base de datos SQLite.
        # Inserta en las tablas: Proteins, ProteinShortNames y ProteinAlternativeNames.
        # Ignora registros duplicados usando `INSERT OR IGNORE`.

        with Database(self.db_path) as cursor:
            for p in proteins:
                cursor.execute("""
                    INSERT OR IGNORE INTO Proteins (accession_number, name, full_name, organism, gene, description, sequence, length)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p["accession_number"],
                    p["name"],
                    p["full_name"],
                    p["organism"],
                    p["gene"],
                    p["description"],
                    p["sequence"],
                    int(p["length"]) if p["length"] else None
                ))

                for s in p["short_names"]:
                    cursor.execute("""
                        INSERT INTO ProteinShortNames (accession_number, short_name)
                        VALUES (?, ?)
                    """, (p["accession_number"], s))

                for a in p["alternative_names"]:
                    cursor.execute("""
                        INSERT INTO ProteinAlternativeNames (accession_number, alternative_name)
                        VALUES (?, ?)
                    """, (p["accession_number"], a))

        print("[✓] Datos insertados en la base de datos.")

def main():
    # Punto de entrada del script.
    # Solicita una query al usuario, busca proteínas relacionadas y ejecuta el flujo completo:
    # descarga, parseo, guardado en XML e inserción en la base de datos.

    query = input("🔍 Ingresa una query para buscar proteínas en UniProt: ").strip()
    pipeline = UniProtPipeline()
    accessions, name_prefix = pipeline.fetch_accessions(query)

    if not accessions:
        return

    output_xml = f"data/processed/{name_prefix}_data.xml"
    asyncio.run(pipeline.fetch_all_async(accessions, output_xml))

if __name__ == "__main__":
    main()