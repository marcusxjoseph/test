# -*- coding: utf-8 -*-
import csv
import json
import sys
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
import uuid
import zipfile

def parse_input(file_path):
    if file_path.endswith(".json"):
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    elif file_path.endswith(".csv"):
        with open(file_path, newline='', encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            row = next(reader)
            return {
                "glaeubiger": {
                    "name": row["glaeubiger_name"],
                    "strasse": row["glaeubiger_strasse"],
                    "hausnummer": row["glaeubiger_hausnummer"],
                    "plz": row["glaeubiger_plz"],
                    "ort": row["glaeubiger_ort"]
                },
                "schuldner": {
                    "name": row["schuldner_name"],
                    "strasse": row["schuldner_strasse"],
                    "hausnummer": row["schuldner_hausnummer"],
                    "plz": row["schuldner_plz"],
                    "ort": row["schuldner_ort"]
                },
                "forderung": {
                    "hauptforderung": float(row["hauptforderung"]),
                    "gegenstand": row.get("gegenstand", "Forderung aus Vertrag")
                },
                "amtsgericht": row.get("amtsgericht", "Zentrales Mahngericht")
            }
    else:
        raise ValueError("Nur .json oder .csv werden unterstützt.")

def generate_eda_xml(data):
    ns = "http://www.egvp.de/Nachrichtentypen/EDA/1.4"
    ET.register_namespace('', ns)
    root = ET.Element(f"{{{ns}}}Mahnantrag")
    root.set("verfahrensart", "Mahn")
    root.set("version", "1.4")
    root.set("dateiID", str(uuid.uuid4()))
    root.set("erstellungszeitpunkt", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))

    header = ET.SubElement(root, f"{{{ns}}}Header")
    ET.SubElement(header, f"{{{ns}}}Absender").text = data['glaeubiger']['name']
    ET.SubElement(header, f"{{{ns}}}Empfaenger").text = data.get('mahngericht', 'Zentrales Mahngericht')

    parteien = ET.SubElement(root, f"{{{ns}}}Parteien")
    g = ET.SubElement(parteien, f"{{{ns}}}Partei", parteiTyp="Antragsteller", parteiNr="G1")
    ET.SubElement(g, f"{{{ns}}}Name").text = data['glaeubiger']['name']
    a = ET.SubElement(g, f"{{{ns}}}Anschrift")
    ET.SubElement(a, f"{{{ns}}}Strasse").text = data['glaeubiger']['strasse']
    ET.SubElement(a, f"{{{ns}}}Hausnummer").text = data['glaeubiger']['hausnummer']
    ET.SubElement(a, f"{{{ns}}}Postleitzahl").text = data['glaeubiger']['plz']
    ET.SubElement(a, f"{{{ns}}}Ort").text = data['glaeubiger']['ort']

    s = ET.SubElement(parteien, f"{{{ns}}}Partei", parteiTyp="Antragsgegner", parteiNr="S1")
    ET.SubElement(s, f"{{{ns}}}Name").text = data['schuldner']['name']
    a = ET.SubElement(s, f"{{{ns}}}Anschrift")
    ET.SubElement(a, f"{{{ns}}}Strasse").text = data['schuldner']['strasse']
    ET.SubElement(a, f"{{{ns}}}Hausnummer").text = data['schuldner']['hausnummer']
    ET.SubElement(a, f"{{{ns}}}Postleitzahl").text = data['schuldner']['plz']
    ET.SubElement(a, f"{{{ns}}}Ort").text = data['schuldner']['ort']

    fds = ET.SubElement(root, f"{{{ns}}}Forderungen")
    hf = ET.SubElement(fds, f"{{{ns}}}Forderung", forderungstyp="Hauptforderung", forderungID="F1")
    ET.SubElement(hf, f"{{{ns}}}GlaeubigerRef").text = "G1"
    ET.SubElement(hf, f"{{{ns}}}SchuldnerRef").text = "S1"
    ET.SubElement(hf, f"{{{ns}}}Betrag", waehrung="EUR").text = str(data['forderung']['hauptforderung'])
    ET.SubElement(hf, f"{{{ns}}}Gegenstand").text = data['forderung'].get('gegenstand', 'Forderung aus Vertrag')

    verfahren = ET.SubElement(root, f"{{{ns}}}Verfahren")
    ET.SubElement(verfahren, f"{{{ns}}}Amtsgericht").text = data.get('amtsgericht', 'Zentrales Mahngericht')
    ET.SubElement(verfahren, f"{{{ns}}}Verfahrensgegenstand").text = "Mahnverfahren"
    ET.SubElement(verfahren, f"{{{ns}}}Verfahrensart").text = "Antrag auf Erlass eines Mahnbescheids"
    ET.SubElement(verfahren, f"{{{ns}}}Antragstyp").text = "NormalerMahnantrag"

    return ET.ElementTree(root)

def write_manifest(xml_filename):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Manifest xmlns="http://www.egvp.de/namespace/20040922">
  <Item>
    <Filename>{xml_filename}</Filename>
    <ContentType>text/xml</ContentType>
    <Description>EDA-Mahnantrag XML-Datei</Description>
  </Item>
</Manifest>
'''

def fixed_blocks(data, block_size=128):
    lines = []
    for i in range(0, len(data), block_size):
        lines.append(data[i:i+block_size].ljust(block_size))
    return lines

def create_eda_zip(tree, base_name):
    tmp_path = Path("/tmp")
    xml_name = f"{base_name}.xml"
    xml_path = tmp_path / xml_name
    tree.write(xml_path, encoding='utf-8', xml_declaration=True)

    eda_inf_dir = tmp_path / "EDA-INF"
    eda_inf_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = eda_inf_dir / "manifest.xml"
    manifest_path.write_text(write_manifest(xml_name), encoding="utf-8")

    zip_path = Path.cwd() / f"{base_name}.zip"
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        zipf.write(xml_path, arcname=xml_name)
        zipf.write(manifest_path, arcname="EDA-INF/manifest.xml")
    return zip_path

def create_eda_file(tree, base_name):
    xml_bytes = ET.tostring(tree.getroot(), encoding="utf-8").decode("utf-8")
    xml_blocks = fixed_blocks(xml_bytes)
    aa = "AA" + "MAHNV.EDA".ljust(15) + "V04".ljust(3) + "01".ljust(2) + " " * (128 - 22)
    bb = "BB" + "Ende der Datei".ljust(125)
    eda_lines = [aa] + xml_blocks + [bb]
    eda_text = "\n".join(eda_lines)
    eda_path = Path.cwd() / f"{base_name}.eda"
    eda_path.write_text(eda_text, encoding="utf-8")
    return eda_path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Nutzung: python3 eda_generator.py <datei.csv|json>")
        sys.exit(1)

    input_file = sys.argv[1]
    base_name = Path(input_file).stem
    data = parse_input(input_file)
    xml_tree = generate_eda_xml(data)
    zip_file = create_eda_zip(xml_tree, base_name)
    eda_file = create_eda_file(xml_tree, base_name)

    print(f"✅ ZIP-Datei: {zip_file}")
    print(f"✅ EDA-Datei (mit AA/BB): {eda_file}")