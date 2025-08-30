import sqlite3
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import csv
import math
import os

def analyzeSQL(file_path):
    tables = {}
    relationships = {}

    conn = sqlite3.connect(file_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_names = cursor.fetchall()

    for table in tables_names:
        table_name = table[0]
        print(f"Table Name: {table_name}")
        cursor.execute(f"PRAGMA table_info('{table_name}');")
        columns = cursor.fetchall()

        tables[table_name] = []
        primary_keys = set()
        foreign_keys = set()
        for col in columns:
            col_id, name, dtype, notnull, dflt_value, pk = col
            tables[table_name].append({
                'name': name,
                'type': dtype,
                'not_null': bool(notnull),
                'default': dflt_value,
                'primary_key': bool(pk)
            })
            if pk:
                primary_keys.add(name)

            # Print column info
            info = f"  - {name} ({dtype})"
            if pk: info += " PRIMARY KEY"
            if notnull: info += " NOT NULL"
            if dflt_value is not None: info += f" DEFAULT {dflt_value}"
            print(info)

        # Foreign key info
        cursor.execute(f"PRAGMA foreign_key_list('{table_name}');")
        fkeys = cursor.fetchall()
        if fkeys:
            print("Foreign Keys:")
            relationships[table_name] = []
            for fkey in fkeys:
                _, _, ref_table, from_col, to_col, *_ = fkey
                relation = {
                    'from_column': from_col,
                    'to_table': ref_table,
                    'to_column': to_col
                }
                relationships[table_name].append(relation)
                print(f"    - {from_col} ➜ {ref_table}.{to_col}")
                foreign_keys.add(from_col)
    conn.close()

    return tables, relationships

def create_drawiio(tables, relationships):
    for tablename, table in tables:
        mxfile = ET.Element("mxfile", host="app.diagrams.net")
        diagram = ET.SubElement(mxfile, "diagram", name="ERD")
        graph = ET.Element("mxGraphModel")
        root = ET.SubElement(graph, "root")

    id_counter = 2
    shape_ids = {}
    entity_positions = {}

    def new_id():
        nonlocal id_counter
        id_counter += 1
        return str(id_counter)

    def add_shape(label, style, x, y, w, h):
        sid = new_id()
        cell = ET.Element("mxCell",{
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
        return(sid)

    def add_edge(source_id, target_id, label=""):
        eid = new_id()
        cell = ET.Element("mxCell", {
            "id": eid,
            "value": label,
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

    entity_nudge = 20  # small stagger to avoid full overlap
    base_x, base_y = 0, 0
    i_entity = 0

    for table_name, data in tables.items():
        table_type = data["type"]
        if table_type == "strong":
            style = "shape=rectangle;whiteSpace=wrap;html=1;"
        elif table_type == "weak":
            style = "shape=ext;margin=3;double=1;whiteSpace=wrap;html=1;align=center;"
        elif table_type == "associative":
            style = "shape=associativeEntity;whiteSpace=wrap;html=1;align=center;"
        else:
            style = "shape=rectangle;whiteSpace=wrap;html=1;"

        # drop the entity at (0, i*20)
        entity_id = add_shape(
            f"{table_name} ({table_type})",
            style,
            x=base_x,
            y=base_y + i_entity * entity_nudge,
            w=140,
            h=40
        )
        shape_ids[table_name] = entity_id
        i_entity += 1

        # attributes: same trick — small offset; auto-layout will fix later
        attr_offset_x = 200
        attr_offset_y = 0
        i_attr = 0
        for col_data in data["columns"]:
            if col_data["role"] == "FK":
                continue
            label = f"<u>{col_data['name']}</u>" if col_data["role"] == "PK" else col_data["name"]
            attr_id = add_shape(
                label,
                "ellipse;whiteSpace=wrap;html=1;",
                x=base_x + attr_offset_x,
                y=base_y + i_entity * entity_nudge + i_attr * 5,
                w=120,
                h=30
            )
            add_edge(entity_id, attr_id)
            i_attr += 1


if __name__ == "__main__":
    file_path = "Spider Dataset2/Daniel/film_rank/film_rank.sqlite"
    if not os.path.exists(file_path):
        print(f"Could not find file {file_path}")
    else:
        print(f"Opening {file_path}")
        tables, relationships = analyzeSQL(file_path)

