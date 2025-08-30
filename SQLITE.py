import sqlite3
import xml.etree.ElementTree as ET
from xml.dom import minidom
import csv
import math
import os
import traceback

DEBUG = True

def debug_print(*args):
    if DEBUG:
        print("[DEBUG]:", *args)

def create_drawio_from_csv(tables, fks, output_file="conceptual_erd.drawio"):

    # Create draw.io XML
    debug_print("Initializing mxGraph XML structure")
    mxfile = ET.Element("mxfile", host="app.diagrams.net")
    diagram = ET.SubElement(mxfile, "diagram", name="ERD")
    graph = ET.Element("mxGraphModel")
    root = ET.SubElement(graph, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    id_counter = 2
    shape_ids = {}
    entity_positions = {}

    def new_id():
        nonlocal id_counter
        id_counter += 1
        return str(id_counter)

    def add_shape(label, style, x, y, w, h):
        sid = new_id()
        debug_print("add_shape", {"id": sid, "label": label, "x": x, "y": y, "w": w, "h": h, "style": style})
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

    def add_edge(source_id, target_id):
        eid = new_id()
        debug_print("add_edge", {"id": eid, "source": source_id, "target": target_id})
        cell = ET.Element("mxCell", {
            "id": eid,
            "style": "edgeStyle=orthogonalEdgeStyle;endArrow=none;html=1;rounded=0;",
            "edge": "1",
            "parent": "1",
            "source": source_id,
            "target": target_id
        })
        geometry = ET.Element("mxGeometry", {
            "relative": "1",
            "as": "geometry"
        })
        cell.append(geometry)
        root.append(cell)
        return eid

    # Grid-based layout
    num_tables = len(tables)
    debug_print("Layout prep", {"num_tables": num_tables})

    if num_tables == 0:
        debug_print(f"No tables to draw")
        return

    cols = math.ceil(math.sqrt(num_tables))
    rows = math.ceil(num_tables / cols) if cols else 0
    x_spacing = 300
    attr_spacing = 40
    max_per_row = 3  # how many entities per row
    cur_y = 100
    x = 100
    col = 0
    max_height_in_row = 0

    for table_name, data in tables.items():
        num_attrs = len(data["columns"])
        entity_height = 60 + num_attrs * attr_spacing
        max_height_in_row = max(max_height_in_row, entity_height)

        # Start a new row if necessary
        if col >= max_per_row:
            col = 0
            x = 100
            cur_y += max_height_in_row + 100  # space between rows
            max_height_in_row = entity_height  # reset for new row
        elif col > 0:
            x += x_spacing

        col += 1

        # Draw entity box
        label = table_name
        table_type = data["type"]

        if table_type == "strong":
            style = "shape=rectangle;whiteSpace=wrap;html=1;"
        elif table_type == "weak":
            style = "shape=ext;margin=3;double=1;whiteSpace=wrap;html=1;align=center;"
        elif table_type == "associative":
            style = "shape=associativeEntity;whiteSpace=wrap;html=1;align=center;"
        else:
            style = "shape=rectangle;whiteSpace=wrap;html=1;"

        debug_print("Entity placement", {"table": table_name, "type": table_type, "x": x, "y": cur_y, "attrs": num_attrs})
        entity_id = add_shape(label, style, x, cur_y, 140, 40)
        shape_ids[table_name] = entity_id
        entity_positions[table_name] = (x, cur_y)

        # Draw attributes
        attr_y = cur_y + 60
        for col_data in data["columns"]:
            name = col_data["name"]
            role = col_data["role"]
            if role == "FK":
                debug_print("Skip drawing FK attribute", {"table": table_name, "column": name})
                continue

            label_attr = f"<u>{name}</u>" if role == "PK" else name
            style_attr = "ellipse;whiteSpace=wrap;html=1;"
            debug_print("Attribute placement", {"table": table_name, "column": name, "role": role, "x": x + 180, "y": attr_y})
            attr_id = add_shape(label_attr, style_attr, x + 180, attr_y, 120, 30)
            add_edge(entity_id, attr_id)
            attr_y += attr_spacing

    # Draw relationships in grid below entity rows
    rel_cols = 4
    rel_x_spacing = 250
    rel_y_spacing = 150
    rel_start_y = cur_y + max_height_in_row + 150

    debug_print("Relationship layout params", {
        "rel_cols": rel_cols, "rel_x_spacing": rel_x_spacing, "rel_y_spacing": rel_y_spacing, "rel_start_y": rel_start_y
    })

    for i, rel in enumerate(fks):
        col = i % rel_cols
        row = i // rel_cols
        rx = 150 + col * rel_x_spacing
        ry = rel_start_y + row * rel_y_spacing

        label = f"{rel['from_table']}→ {rel['to_table']}.{rel['to_column']}"
        debug_print("Relationship diamond placement", {"i": i, "label": label, "x": rx, "y": ry})

        diamond_id = add_shape(label, "rhombus;whiteSpace=wrap;html=1;", rx, ry, 100, 60)

        from_id = shape_ids.get(rel["from_table"])
        to_id = shape_ids.get(rel["to_table"])
        if from_id is None or to_id is None:
            debug_print("WARNING: Missing entity shape for relationship endpoints", {
                "from_table": rel["from_table"], "to_table": rel["to_table"], "from_id": from_id, "to_id": to_id
            })

        add_edge(from_id, diamond_id)
        add_edge(diamond_id, to_id)

    # Finalize XML
    diagram.append(graph)
    xml_bytes = ET.tostring(mxfile)
    try:
        xml_str = minidom.parseString(xml_bytes).toprettyxml(indent="  ")
        debug_print("XML generated", {"length_chars": len(xml_str)})
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(xml_str)
        print(f"Draw.io file saved: {output_file}")
    except Exception as e:
        debug_print("Error finalizing/writing XML:", e)
        traceback.print_exc()
        raise

def analyze_sqlite_schema(sqlite_file):
    debug_print("==> Enter analyze_sqlite_schema", {"sqlite_file": sqlite_file})
    try:
        conn = sqlite3.connect(sqlite_file)
    except Exception as e:
        debug_print("Failed to connect to SQLite file", {"sqlite_file": sqlite_file, "error": e})
        traceback.print_exc()
        raise

    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        table_names = [row[0] for row in cursor.fetchall()]
        debug_print("Tables found:", table_names)

        tables = {}
        fk_relations = []

        for table in table_names:
            try:
                debug_print(f"-- Analyzing table: {table}")

                cursor.execute(f"PRAGMA foreign_key_list('{table}')")
                fks = cursor.fetchall()
                debug_print(f"Foreign keys in {table} (raw):", fks)
                fk_list = [(fk[3], fk[2], fk[4]) for fk in fks]  # (from_col, to_table, to_col)
                if fk_list:
                    debug_print(f"Foreign keys in {table} (parsed):", fk_list)

                cursor.execute(f"PRAGMA table_info('{table}')")
                cols = cursor.fetchall()
                debug_print(f"Columns in {table}:", cols)

                pk_columns = set()
                all_columns = []
                column_roles = {}

                for col in cols:
                    col_name = col[1]
                    is_pk = bool(col[5])
                    if is_pk:
                        pk_columns.add(col_name)
                    all_columns.append(col_name)
                    column_roles[col_name] = "ATTR"

                debug_print(f"Initial roles for {table}:", {"pk_columns": list(pk_columns), "all_columns": all_columns})

                fk_columns = set()
                for from_col, to_table, to_col in fk_list:
                    fk_columns.add(from_col)
                    if from_col in pk_columns:
                        column_roles[from_col] = "PK+FK"
                    else:
                        column_roles[from_col] = "FK"
                    fk_relations.append({
                        "from_table": table,
                        "from_column": from_col,
                        "to_table": to_table,
                        "to_column": to_col
                    })

                for col in pk_columns:
                    if column_roles[col] != "PK+FK":
                        column_roles[col] = "PK"

                debug_print(f"Computed roles for {table}:", column_roles)

                # Classification logging
                if pk_columns & fk_columns:
                    table_type = "weak"
                    reason = "some PK columns are also FK columns"
                else:
                    table_type = "strong"
                    reason = "default strong (PK independent of FK)"

                debug_print(f"Entity classification for {table}:", {"type": table_type, "reason": reason})

                tables[table] = {
                    "type": table_type,
                    "columns": [{"name": col, "role": column_roles[col]} for col in all_columns]
                }
            except Exception as e_table:
                debug_print(f"Error while analyzing table {table}:", e_table)
                traceback.print_exc()
                raise

        debug_print("Schema analysis complete", {
            "tables_count": len(tables),
            "fk_relations_count": len(fk_relations)
        })
        if fk_relations[:3]:
            debug_print("Sample fk_relations (up to 3):", fk_relations[:3])

        return tables, fk_relations
    finally:
        conn.close()
        debug_print("SQLite connection closed")

if __name__ == "__main__":
    directory = "../Spider Dataset2/Daniel/apartment_rentals"
    debug_print("Script start. Walking directory:", directory)

    for foldername, subfolders, filenames in os.walk(directory):
        debug_print("Visiting folder", {"folder": foldername, "files_count": len(filenames)})
        for filename in filenames:
            if filename.endswith(".sqlite"):
                file_path = os.path.join(foldername, filename)
                print(f"Processing {file_path}")
                debug_print("Processing .sqlite file", file_path)

                tables_csv_path = os.path.join(foldername, "table_metadata.csv")
                fks_csv_path = os.path.join(foldername, "foreign_keys.csv")
                drawio_path = os.path.join(foldername, "conceptual_erd.drawio")
                debug_print("Resolved paths", {
                    "tables_csv_path": tables_csv_path,
                    "fks_csv_path": fks_csv_path,
                    "drawio_path": drawio_path
                })

                tables, fk_relations = analyze_sqlite_schema(file_path)
                create_drawio_from_csv(tables, fk_relations, drawio_path)

    debug_print("Script completed")
