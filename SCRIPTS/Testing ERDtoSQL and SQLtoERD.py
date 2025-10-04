import sqlite3
import os
import pandas as pd
import subprocess
import re
from google import genai
from common.config import instruction
client = genai.Client(api_key="AIzaSyCRBP9yA8mavdaepsouEfpElGCnUIOu4_M")
from Compare import compare_schemas
from ERD_to_SQL import process_erd
def convert_drawio_to_png(input_file, output_file):
    subprocess.run([
        r"C:\Program Files\draw.io\draw.io.exe",
        "--export",
        "--format", "png",
        "--output", output_file,
        input_file
    ])


def create_sqlite(schema, file_path):
  conn = sqlite3.connect(file_path)
  cursor = conn.cursor()
  cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
  tables = cursor.fetchall()

  # Drop each table
  for table in tables:
      cursor.execute(f"DROP TABLE IF EXISTS {table[0]};")

  cursor.executescript(schema)

  conn.commit()
  conn.close()

import xml.etree.ElementTree as ET
import math
from xml.dom import minidom

"""
schema_dict = {
  "Orders": {
    "type": "Strong Entity",  # classification: Strong / Weak / Associative / No PK
    "columns": [              # list of columns in this table
      {
        "cid": 0,             # column id in SQLite
        "name": "order_id",   # column name
        "type": "INTEGER",    # declared data type
        "notnull": 1,         # 1 = NOT NULL, 0 = nullable
        "dflt_value": None,   # default value (if any)
        "pk": 1,              # 1 = part of primary key, 0 = not
        "is_unique": False    # True if part of a UNIQUE index
      },
      ...
    ],
    "foreign_keys": [         # list of FKs this table defines
      {
        "from_column": "customer_id",   # child column in Orders
        "to_table": "Customers",        # parent table
        "to_column": "id",              # parent column
        "on_update": "CASCADE",         # action on update
        "on_delete": "CASCADE",         # action on delete
        "match": "NONE",                # match type (SQLite only supports NONE)
        "cardinality": "N:1",           # your derived relation type
      }
    ],
    "parent_tables": parent_tables

  }
}

"""
import xml.etree.ElementTree as ET
from xml.dom import minidom

def create_drawio(schema_dict, output_file="conceptual_erd.drawio"):
    # --- Setup XML base ---
    mxfile = ET.Element("mxfile", host="app.diagrams.net")
    diagram = ET.SubElement(mxfile, "diagram", name="ERD")
    graph = ET.Element("mxGraphModel")
    root = ET.SubElement(graph, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    id_counter = 2
    shape_ids = {}

    def new_id():
        nonlocal id_counter
        id_counter += 1
        return str(id_counter)

    def add_shape(label, style, x, y, w, h):
        sid = new_id()
        cell = ET.Element("mxCell", {
            "id": sid,
            "value": label,
            "style": style,
            "vertex": "1",
            "parent": "1"
        })
        geometry = ET.Element("mxGeometry", {
            "x": str(x),
            "y": str(y),
            "width": str(w),
            "height": str(h),
            "as": "geometry"
        })
        cell.append(geometry)
        root.append(cell)
        return sid

    def add_edge(source_id, target_id, value=""):
        eid = new_id()
        cell = ET.Element("mxCell", {
            "id": eid,
            "style": "edgeStyle=orthogonalEdgeStyle;endArrow=none;html=1;rounded=0;",
            "edge": "1",
            "value": value,
            "parent": "1",
            "source": source_id,
            "target": target_id
        })
        geometry = ET.Element("mxGeometry", {"relative": "1", "as": "geometry"})
        cell.append(geometry)
        root.append(cell)
        return eid

    num_tables = len(schema_dict)
    if num_tables == 0:
        print("No tables found in schema_dict.")
        return

    max_per_row = 3
    x_spacing = 300
    attr_spacing = 40
    cur_y = 100
    x = 100
    col = 0
    max_height_in_row = 0

    for table_name, data in schema_dict.items():
        num_attrs = len(data["columns"])
        entity_height = 60 + num_attrs * attr_spacing
        max_height_in_row = max(max_height_in_row, entity_height)

        if col >= max_per_row:
            col = 0
            x = 100
            cur_y += max_height_in_row + 100
            max_height_in_row = entity_height
        elif col > 0:
            x += x_spacing
        col += 1

        # Pick style
        table_type = data["type"].lower()
        if "weak" in table_type:
            style = "shape=ext;double=1;whiteSpace=wrap;html=1;"
        elif "associative" in table_type:
            style = "shape=associativeEntity;whiteSpace=wrap;html=1;"
        else:
            style = "shape=rectangle;whiteSpace=wrap;html=1;"

        entity_id = add_shape(table_name, style, x, cur_y, 140, 40)
        shape_ids[table_name] = entity_id

        # Add attributes
        fk_cols = {fk["from_column"] for fk in data["foreign_keys"]}
        pk_cols = [col["name"] for col in data["columns"] if col["pk"] > 0]

        attr_y = cur_y + 60
        for col_data in data["columns"]:
            name = col_data["name"]
            role = "Attr"
            if col_data["pk"] > 0:
                role = "PK"
            if name in fk_cols:
                role = "FK" if role == "Attr" else "PK+FK"

            # Don’t draw FK-only attributes
            if "FK" not in role:
                label_attr = f"<u>{name}</u>" if role.startswith("PK") else name
                attr_id = add_shape(label_attr, "ellipse;whiteSpace=wrap;html=1;", x + 180, attr_y, 120, 30)
                add_edge(entity_id, attr_id)
                attr_y += attr_spacing

    # ---------------------------
    # PASS 2: RELATIONSHIPS
    # ---------------------------
    rel_x_start = 150
    rel_y_start = cur_y + max_height_in_row + 150
    rel_x_spacing = 250
    rel_y_spacing = 150
    rel_index = 0

    for table_name, data in schema_dict.items():
        parent_tables = data.get("parent_tables", [])
        table_type = data["type"].lower()

        # Normal FKs
        for fk in data["foreign_keys"]:
            from_table = table_name
            to_table = fk["to_table"]

            # Skip parent tables (handled as identifying relationships)
            if to_table in parent_tables:
                continue

            rx = rel_x_start + (rel_index % 4) * rel_x_spacing
            ry = rel_y_start + (rel_index // 4) * rel_y_spacing
            rel_index += 1

            label = f"{from_table}.{fk['from_column']} → {to_table}.{fk['to_column']} ({fk.get('cardinality','N:1')})"
            diamond_id = add_shape(label, "rhombus;whiteSpace=wrap;html=1;", rx, ry, 120, 60)

            from_id = shape_ids.get(from_table)
            to_id = shape_ids.get(to_table)
            if from_id and to_id:
                left_card, right_card = fk.get("cardinality", "N:1").split(":")
                add_edge(from_id, diamond_id, left_card)
                add_edge(diamond_id, to_id, right_card)

        # Identifying (weak) relationships
        for parent_table in parent_tables:
            rx = rel_x_start + (rel_index % 4) * rel_x_spacing
            ry = rel_y_start + (rel_index // 4) * rel_y_spacing
            rel_index += 1

            style = "rhombus;whiteSpace=wrap;html=1;"
            label = f"{table_name} → {parent_table}"
            if "weak" in table_type:
                style = "rhombus;double=1;whiteSpace=wrap;html=1;"
                label = f"Identifying {table_name} → {parent_table}"

            diamond_id = add_shape(label, style, rx, ry, 120, 60)

            from_id = shape_ids.get(table_name)
            to_id = shape_ids.get(parent_table)
            if from_id and to_id:
                add_edge(from_id, diamond_id, "N")
                add_edge(diamond_id, to_id, "1")

    # Finalize XML
    diagram.append(graph)
    xml_bytes = ET.tostring(mxfile)
    xml_str = minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"Draw.io file created: {output_file}")



def analyze_sqlite_schema(sqlite_file):
    conn = sqlite3.connect(sqlite_file)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    table_names = [row[0] for row in cursor.fetchall()]

    schema_dict = {}
    df = pd.DataFrame(columns=["folder", "differences", "equivalent?"])
    for table in table_names:
        cursor.execute(f"PRAGMA foreign_key_list('{table}')")
        fks = cursor.fetchall()
        fk_df = pd.DataFrame(fks, columns=[
            "id", "seq", "ref_table", "from_col", "to_col", "on_update", "on_delete", "match"
        ]) if fks else pd.DataFrame(columns=[
            "id", "seq", "ref_table", "from_col", "to_col", "on_update", "on_delete", "match"
        ])

        cursor.execute(f"PRAGMA table_info('{table}')")
        cols = cursor.fetchall()
        col_df = pd.DataFrame(cols, columns=["cid", "name", "type", "notnull", "dflt_value", "pk"])

        cursor.execute(f"PRAGMA index_list('{table}')")
        indexes = cursor.fetchall()

        unique_cols = []
        for idx in indexes:
            idx_name = idx[1]
            is_unique = bool(idx[2])
            if is_unique:
                cursor.execute(f"PRAGMA index_info('{idx_name}')")
                idx_cols = cursor.fetchall()
                unique_cols.extend([c[2] for c in idx_cols])

        #debugging
        col_df["is_unique"] = col_df["name"].apply(lambda x: x in unique_cols)
        print(f"Columns for {table} are: \n {col_df}")

        pk_cols = set(col_df.loc[col_df["pk"] > 0, "name"])
        fk_dict = {}
        for row in fk_df.itertuples(index=False):
            fk_dict[row.from_col] = row.ref_table
        fk_in_pk_dict = {col: ref for col, ref in fk_dict.items() if col in pk_cols}
        parent_tables = list(set(fk_in_pk_dict.values()))
        print(f"Foreign keys in PKs for {table} are: \n {fk_in_pk_dict}")
        if len(pk_cols) == 0:
            table_type = "Entity (No PK)"
        elif len(fk_in_pk_dict) == 0:
            table_type = "Strong Entity"
        else:
            if len(parent_tables) == 1:
                table_type = "Weak Entity"
            elif len(parent_tables) >= 2:
                table_type = "Associative Entity"
            else:
                table_type = "Entity"


        schema_dict[table] = {
            "type": table_type,
            "columns": col_df.to_dict(orient="records"),
            "foreign_keys": [],
            "parent_tables": parent_tables
        }

        for _, fk in fk_df.iterrows():

            from_col = fk["from_col"]
            to_table = fk["ref_table"]
            to_col = fk["to_col"]

            # Cardinality
            relation_type = "N:1"

            schema_dict[table]["foreign_keys"].append({
                "from_column": from_col,
                "to_table": to_table,
                "to_column": to_col,
                "on_update": fk["on_update"],
                "on_delete": fk["on_delete"],
                "match": fk["match"],
                "cardinality": relation_type,

            })
        print(f"schema_dict : {schema_dict}")

    conn.close()
    return schema_dict

directory = "../Spider Dataset(Clean)"

"""for dirpath, dirnames, filenames in os.walk(directory):
    for filename in filenames:
        if filename.endswith(".sql"):
            file_path = os.path.join(dirpath, filename)

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                schema = f.read()

            sqlite_path = os.path.join(dirpath, filename.replace(".sql", ".sqlite"))
            create_sqlite(schema, sqlite_path)

            schema_dict = analyze_sqlite_schema(sqlite_path)

            out_file = os.path.join(dirpath, filename.replace(".sql", "(SQLtoERD).drawio"))
            create_drawio(schema_dict, out_file)"""
def extract_step_sql(text):

    parts = text.split("=== STEP 5 — BINARY M:N (SQL) ===")

    if len(parts) > 1:
        step5_section = parts[1]

        step5_sql = step5_section.split("=== EXPLANATION / ASSUMPTIONS / ANOMALIES FOR STEP 5===")[0]

        # Strip leading/trailing whitespace
        step5_sql = step5_sql.strip()

        return step5_sql.strip().replace("```sql","").replace("```","")
    else:
        return ""

import os
import pandas as pd
import sqlite3
from Compare import compare_schemas
from ERD_to_SQL import process_erd

def process_directory(dirpath, filenames):
    # Step 1: find schema.sql (or fallback to foldername.sql)
    schema_path = os.path.join(dirpath, "schema.sql")
    if not os.path.exists(schema_path):
        folder_name = os.path.basename(dirpath)
        alt_schema = os.path.join(dirpath, f"{folder_name}.sql")
        if os.path.exists(alt_schema):
            schema_path = alt_schema

    if not os.path.exists(schema_path):
        print(f"Skipping {dirpath}: no schema.sql or {folder_name}.sql found")
        return None

    # Step 2: create SQLite database
    sqlite_path = os.path.join(dirpath, "schema.sqlite")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_text = f.read()
    create_sqlite(schema_text, sqlite_path)

    # Step 3: analyze schema → schema_dict
    schema_dict = analyze_sqlite_schema(sqlite_path)
    os.remove(sqlite_path)

    # Step 4: generate new drawio from schema_dict
    drawio_file = os.path.join(dirpath, "schema(SQLtoERD).drawio")
    create_drawio(schema_dict, drawio_file)

    # Step 5: regenerate SQL from ERD
    control_case_path = os.path.join(dirpath, "ControlCase.sql")
    control_sql = process_erd(drawio_file, control_case_path)

    # Step 6: compare original SQL vs regenerated SQL
    control_diff, control_equivalent = compare_schemas(schema_text, control_sql)

    return {
        "folder": dirpath,
        "control_sql": control_sql,
        "control differences": control_diff,
        "control_equivalent?": control_equivalent,
        "original": schema_text
    }

def main(directory):
    output_file = "control_results.csv"

    if os.path.exists(output_file):
        df = pd.read_csv(output_file)
        processed_folders = set(df["folder"])
    else:
        df = pd.DataFrame()
        processed_folders = set()

    for dirpath, dirnames, filenames in os.walk(directory):
        if dirpath in processed_folders:
            print(f"Skipping {dirpath}, already processed")
            continue

        result = process_directory(dirpath, filenames)
        if result:
            df = pd.concat([df, pd.DataFrame([result])], ignore_index=True)
            df.to_csv(output_file, index=False)
            print(f"Saved control results for {dirpath}")



if __name__ == "__main__":
    main("../Spider Dataset(Clean)/Daniel")
