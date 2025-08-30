import re
import sqlparse
import xml.etree.ElementTree as ET
from xml.dom import minidom

import re

import re

def extract_create_table_blocks(sql_code):
    removed_blocks = []
    insert_count = 0

    patterns = [
        (r'(PRAGMA.*?;\s*)', True),
        (r'(INSERT INTO.*?;\s*)', False),  # Don't store, just count
        (r'(CREATE TRIGGER.*?;\s*)', True),
        (r'(CREATE INDEX.*?;\s*)', True),
        (r'(UPDATE.*?;\s*)', True)
    ]

    for pattern, keep in patterns:
        matches = re.findall(pattern, sql_code, flags=re.IGNORECASE | re.DOTALL)
        if pattern.startswith('(INSERT INTO'):
            insert_count += len(matches)
        elif keep:
            removed_blocks.extend(matches)
        sql_code = re.sub(pattern, '', sql_code, flags=re.IGNORECASE | re.DOTALL)

    create_pattern = r'CREATE TABLE.*?\(.*?\);'
    create_blocks = re.findall(create_pattern, sql_code, flags=re.IGNORECASE | re.DOTALL)

    return "\n\n".join(create_blocks), "\n\n".join(removed_blocks), insert_count


def smart_split_columns(column_block):
    columns = []
    current = ''
    parens = 0

    for char in column_block:
        if char == '(':
            parens += 1
        elif char == ')':
            parens -= 1
        elif char == ',' and parens == 0:
            columns.append(current.strip())
            current = ''
            continue
        current += char

    if current.strip():
        columns.append(current.strip())
    return columns


def parse_sql(sql_code):
    print(">>> Parsing CREATE TABLE SQL blocks...")
    tables = {}
    foreign_keys = []

    statements = sqlparse.parse(sql_code)
    for stmt in statements:
        if not stmt.tokens:
            continue
        stmt_str = str(stmt).strip()
        print("Parsed SQL Statement:\n", stmt_str, "\n")

        match = re.match(r'CREATE TABLE\s+["`]?(?P<name>\w+)["`]?\s*\((?P<cols>.*?)\);', stmt_str, re.IGNORECASE | re.DOTALL)
        if not match:
            print("  Skipping unrecognized CREATE TABLE format.")
            continue

        table_name = match.group("name")
        print(f">>> Processing table: {table_name}")
        column_block = match.group("cols").replace('\n', '').replace('\r', '')
        raw_columns = smart_split_columns(column_block)
        print(f"  Found {len(raw_columns)} column definitions.")

        all_columns = []
        pk_columns = set()
        fk_columns = set()
        raw_column_names = set()

        for line in raw_columns:
            line = line.replace('"', '')
            if line.upper().startswith("FOREIGN KEY"):
                fk_match = re.search(r'FOREIGN KEY\s*\((\w+)\)\s*REFERENCES\s+[`"]?(\w+)[`"]?\s*\((\w+)\)', line,
                                     re.IGNORECASE)
                if fk_match:
                    from_col, ref_table, ref_col = fk_match.groups()
                    foreign_keys.append((table_name, from_col, ref_table, ref_col))
                    fk_columns.add(from_col)
                    print(f"  Foreign Key: {from_col} → {ref_table}({ref_col})")
            elif "PRIMARY KEY" in line.upper():
                # Table-level PRIMARY KEY constraint
                pk_match = re.findall(r'PRIMARY KEY\s*\((.*?)\)', line, re.IGNORECASE)
                if pk_match:
                    pk_cols = [col.strip() for col in pk_match[0].split(',')]
                    pk_columns.update(pk_cols)
                    print(f"  Primary Key(s): {pk_cols}")
            else:
                # Column definition (possibly with inline PK)
                parts = line.split()
                if len(parts) >= 2:
                    col_name = parts[0].strip('`"')
                    raw_column_names.add(col_name)
                    all_columns.append(col_name)

                    if any("PRIMARY KEY" in p.upper() for p in parts[1:]):
                        pk_columns.add(col_name)
                        print(f"  Inline Primary Key: {col_name}")

        # Determine table type
        if pk_columns and pk_columns.issubset(fk_columns):
            table_type = "associative"
        elif pk_columns & fk_columns:
            table_type = "weak"
        else:
            table_type = "strong"

        print(f"  Classified as {table_type} entity.")

        # Assign role to each column
        columns = []
        for col in all_columns:
            if col in pk_columns and col in fk_columns:
                role = "PK+FK"
            elif col in pk_columns:
                role = "PK"
            elif col in fk_columns:
                role = "FK"
            else:
                role = "ATTR"
            columns.append({"name": col, "role": role})

        tables[table_name] = {
            "type": table_type,
            "columns": columns
        }

    print("\n=== Summary of Parsed Tables ===")
    for table_name, data in tables.items():
        print(f"Table: {table_name}")
        print(f"Type: {data['type']}")
        print("Columns:")
        for col in data['columns']:
            print(f"  - {col['name']} ({col['role']})")

    return tables, foreign_keys



def create_drawio(tables, foreign_keys, output_file="conceptual_erd.drawio"):
    mxfile = ET.Element("mxfile", host="app.diagrams.net")
    diagram = ET.SubElement(mxfile, "diagram", name="ERD")
    graph = ET.Element("mxGraphModel")
    root = ET.SubElement(graph, "root")

    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    id_counter = 2
    elements = {}
    spacing_x = 200
    spacing_y = 150
    y_offset = 0

    def add_shape(label, shape, x, y, w, h, style_extra=""):
        nonlocal id_counter
        sid = str(id_counter)
        id_counter += 1
        style_base = {
            "ellipse": "ellipse;whiteSpace=wrap;html=1;",
            "rectangle": "shape=rectangle;whiteSpace=wrap;html=1;",
            "diamond": "rhombus;whiteSpace=wrap;html=1;"
        }[shape]
        cell = ET.Element("mxCell", {
            "id": sid,
            "value": label,
            "style": style_base + style_extra,
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

    def connect(from_id, to_id, label=""):
        nonlocal id_counter
        eid = str(id_counter)
        id_counter += 1
        attributes = {
            "id": eid,
            "edge": "1",
            "source": from_id,
            "target": to_id,
            "parent": "1",
            "style": "edgeStyle=straight;endArrow=none;startArrow=none;html=1;"
        }
        if label:
            attributes["value"] = label
        edge = ET.Element("mxCell", attributes)
        geometry = ET.Element("mxGeometry", {
            "relative": "1",
            "as": "geometry"
        })
        edge.append(geometry)
        root.append(edge)

    for table_name, data in tables.items():
        attrs = data["columns"]
        table_type = data["type"]

        x = 100
        y = y_offset
        shape_type = "rectangle"
        label = table_name

        if table_type == "weak":
            label = f"{table_name} (weak)"
        elif table_type == "associative":
            label = f"{table_name} (assoc)"

        table_id = add_shape(label, shape_type, x, y, 120, 40)
        elements[table_name] = table_id

        attr_y = y + 50
        for attr_name, kind in attrs:
            label = f"<u>{attr_name}</u>" if kind == "PK" else attr_name
            attr_id = add_shape(label, "ellipse", x + 150, attr_y, 100, 40)
            connect(table_id, attr_id)
            attr_y += 50

        y_offset += max(attr_y - y, 150)

    rel_counter = 0
    for src_table, src_col, tgt_table, tgt_col in foreign_keys:
        x_pos = 400 + 150 * rel_counter
        rel_label = f"{src_col} → {tgt_col}"
        rel_id = add_shape(rel_label, "diamond", x_pos, y_offset, 100, 50)
        connect(elements[src_table], rel_id, label="(rename)")
        connect(rel_id, elements[tgt_table], label="(rename)")
        rel_counter += 1

    diagram.append(graph)
    xml_str = minidom.parseString(ET.tostring(mxfile)).toprettyxml(indent="  ")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"Draw.io file saved as: {output_file}")

if __name__ == "__main__":
    input_file = "../input.sql"
    output_file = "../conceptual_erd.drawio"

    with open(input_file, "r", encoding="utf-8") as f:
        sql = f.read()

    schema_sql, removed, insert_count = extract_create_table_blocks(sql)
    # print("=== THESE WERE REMOVED ===")
    # print(removed)
    # print(f'Inserts Removed: {insert_count}')
    tables, foreign_keys = parse_sql(schema_sql)
    create_drawio(tables, foreign_keys, output_file)
