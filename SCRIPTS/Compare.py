from sqlglot.expressions import (
    Create, ColumnDef, Constraint, PrimaryKey,
    ForeignKey, PrimaryKeyColumnConstraint
)
import os
from sqlglot import parse, exp
import re

def clean_sql(sql: str) -> str:
    # --- 1. Remove non-standard quoting ---
    sql = re.sub(r'`([^`]+)`', r'\1', sql)   # strip backticks
    sql = re.sub(r'"([^"]+)"', r'\1', sql)   # strip double quotes

    # --- 2. Normalize datatypes ---
    sql = sql.replace("DATETIME", "TEXT")
    sql = sql.replace("FLOAT NULL", "FLOAT")
    sql = sql.replace('" te', '" text')  # truncated text type

    # --- 3. Fix missing commas between constraints ---
    sql = re.sub(r'\)\s+(FOREIGN KEY)', r'), \1', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\)\s+(UNIQUE)', r'), \1', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\)\s+(CHECK)', r'), \1', sql, flags=re.IGNORECASE)

    # --- 4. Normalize constraint keywords ---
    sql = re.sub(r'foreign key', r'FOREIGN KEY', sql, flags=re.IGNORECASE)
    sql = re.sub(r'references', r'REFERENCES', sql, flags=re.IGNORECASE)
    sql = re.sub(r'primary key', r'PRIMARY KEY', sql, flags=re.IGNORECASE)
    sql = re.sub(r'unique', r'UNIQUE', sql, flags=re.IGNORECASE)
    sql = re.sub(r'check', r'CHECK', sql, flags=re.IGNORECASE)

    return sql



def extract_create_tables(sql_text: str):
    tables = re.findall(r"CREATE TABLE.*?\);", sql_text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = []
    for t in tables:
        t = re.sub(r"\(\d+\)", "", t)   # strip (50), (255), etc.
        t = re.sub(r"\s+", " ", t)      # collapse spaces
        cleaned.append(t.strip())
    return "\n\n".join(cleaned)

def compare_attributes(expr1, expr2):
    def extract_non_fk_columns(expr):
        fk_columns = set()
        all_columns = set()

        for col in expr.find_all(ColumnDef):
            if getattr(col.this, "this", None):
                all_columns.add(col.this.this.lower())

        for fk in expr.find_all(ForeignKey):
            if getattr(fk, "this", None) and getattr(fk.this, "expressions", None):
                for local_col in fk.this.expressions:
                    if hasattr(local_col, "this"):
                        fk_columns.add(local_col.this.lower())

            elif fk.args.get("expressions"):
                for local_col in fk.args["expressions"]:
                    if hasattr(local_col, "this"):
                        fk_columns.add(local_col.this.lower())

            elif getattr(fk, "this", None) and hasattr(fk.this, "this"):
                fk_columns.add(fk.this.this.lower())

            # CASE 4: Constraint-wrapped foreign keys
            elif fk.args.get("this") and hasattr(fk.args["this"], "this"):
                fk_columns.add(fk.args["this"].this.lower())
        # --- Return only non-FK columns ---
        return all_columns - fk_columns

    attributes1 = extract_non_fk_columns(expr1)
    attributes2 = extract_non_fk_columns(expr2)

    only_in_1 = set(attributes1) - set(attributes2)
    only_in_2 = set(attributes2) - set(attributes1)

    results = []
    equivalent = True

    if only_in_1:
        print("  → Only in schema1:", only_in_1)
        results.append("only in schema1: " + str(only_in_1))
        equivalent = False
    if only_in_2:
        print("  → Only in schema2:", only_in_2)
        results.append("only in schema2: " + str(only_in_2))
        equivalent = False

    return results, equivalent


def primary_key_checker(expr1, expr2):
    pk1 = []
    pk2 = []

    # Extract foreign keys and referenced tables
    table1referenced, table1fk_columns = extract_fk_tables(expr1)
    table2referenced, table2fk_columns = extract_fk_tables(expr2)

    # Extract PKs for schema 1
    for col in expr1.this.expressions:
        if col.args.get("constraints"):
            for cons in col.args["constraints"]:
                if isinstance(cons.kind, PrimaryKeyColumnConstraint):
                    pk1.append(col.name)
    for expr in expr1.this.expressions:
        if isinstance(expr, PrimaryKey):
            for pk in expr.expressions:
                pk1.append(pk.this)

    # Extract PKs for schema 2
    for col in expr2.this.expressions:
        if col.args.get("constraints"):
            for cons in col.args["constraints"]:
                if isinstance(cons.kind, PrimaryKeyColumnConstraint):
                    pk2.append(col.name)
    for expr in expr2.this.expressions:
        if isinstance(expr, PrimaryKey):
            for pk in expr.expressions:
                pk2.append(pk.this)

    # Convert to sets for comparison
    pk1_set = set(pk1)
    pk2_set = set(pk2)
    fk1_set = set(table1fk_columns)
    fk2_set = set(table2fk_columns)
    ref1_set = set(table1referenced)
    ref2_set = set(table2referenced)

    # Compare primary keys excluding FK columns
    pk_comparison = (pk1_set - fk1_set) == (pk2_set - fk2_set)

    # Compare referenced tables directly
    ref_comparison = ref1_set == ref2_set

    if pk_comparison and ref_comparison:
        return ["Primary keys and references are the same"], True
    else:
        msg = f"Primary key or reference mismatch:\n  schema1 PKs: {pk1}\n  schema2 PKs: {pk2}\n  schema1 refs: {table1referenced}\n  schema2 refs: {table2referenced}"
        return [msg], False


def extract_fk_tables(expr):
    referenced = []
    fk_columns = []

    for e in expr.this.expressions:
        if isinstance(e, Constraint):
            for constraint in e.expressions:
                if isinstance(constraint, ForeignKey):
                    ref = constraint.args.get("reference")
                    if ref:
                        referenced.append(ref.this.this.this.this)
                    if constraint.name:
                        fk_columns.append(str(constraint.name))
        elif isinstance(e, ForeignKey):
            ref = e.args.get("reference")
            if ref:
                referenced.append(ref.this.this.this.this)
            if e.name:
                fk_columns.append(str(e.name))

    return referenced, fk_columns

def foreign_key_checker(expr1, expr2):
    fk1_tables = set(extract_fk_tables(expr1))
    fk2_tables = set(extract_fk_tables(expr2))

    if fk1_tables == fk2_tables:
        return ["Foreign keys reference the same tables"], True
    else:
        return [f"Foreign key differences:\n  schema1: {fk1_tables}\n  schema2: {fk2_tables}"], False

def strip_datatypes(ast):
    cleaned = []
    for expr in ast:
        expr_copy = expr.copy()
        for column in expr_copy.find_all(ColumnDef):
            column.set("kind", None)
        cleaned.append(expr_copy)
    return cleaned


def get_table_names(ast):
    return [stmt.this.this for stmt in ast if isinstance(stmt, Create)]


def get_create_node_for_table(ast, table_name):
    for stmt in ast:
        if isinstance(stmt, Create) and stmt.this.this == table_name:
            return stmt
    return None


def compare_schemas(schema1_str, schema2_str):
    schema1_str, schema2_str = clean_sql(extract_create_tables(schema1_str)), clean_sql(extract_create_tables(schema2_str))
    overall_equivalent = True
    results = []

    ast1 = parse(schema1_str)
    ast2 = parse(schema2_str)

    ast1_clean = strip_datatypes(ast1)
    ast2_clean = strip_datatypes(ast2)

    tables1 = set(get_table_names(ast1_clean))
    tables2 = set(get_table_names(ast2_clean))

    only_in_1 = tables1 - tables2
    only_in_2 = tables2 - tables1
    common_tables = tables1 & tables2

    if only_in_1:
        results.append(f"Tables only in schema1: {only_in_1}")
        overall_equivalent = False
    if only_in_2:
        results.append(f"Tables only in schema2: {only_in_2}")
        overall_equivalent = False
    if not common_tables:
        results.append("No common tables to compare.")
        return results, False

    for table in common_tables:
        results.append(f"\nComparing table: {table}")
        table_equivalent = True

        table_clean_1 = get_create_node_for_table(ast1_clean, table)
        table_clean_2 = get_create_node_for_table(ast2_clean, table)
        table_orig_1 = get_create_node_for_table(ast1, table)
        table_orig_2 = get_create_node_for_table(ast2, table)


        attr_diff, attrs_eq = compare_attributes(table_clean_1, table_clean_2)
        if not attrs_eq:
            table_equivalent = False
            results.extend(attr_diff)

        pk_diff, pk_eq = primary_key_checker(table_orig_1, table_orig_2)
        if not pk_eq:
            table_equivalent = False
            results.extend(pk_diff)

        fk_diff, fk_eq = foreign_key_checker(table_orig_1, table_orig_2)
        if not fk_eq:
            table_equivalent = False
            results.extend(fk_diff)

        if not table_equivalent:
            overall_equivalent = False
    if overall_equivalent:
        results = []

    return results, overall_equivalent



if __name__ == "__main__":
    schema1 = """
CREATE TABLE Apartment_Buildings (
    building_id VARCHAR(255),
    building_short_name VARCHAR(255),
    building_full_name VARCHAR(255),
    building_description VARCHAR(255),
    building_address VARCHAR(255),
    building_manager VARCHAR(255),
    building_phone VARCHAR(255),
    PRIMARY KEY (building_id)
);

-- Added FK to Apartment_Buildings because Apartments is the many side.
-- Weak 1�Many: PK = owner PK + partial key

CREATE TABLE Apartments (
    apt_id VARCHAR(255),
    apt_type_code VARCHAR(255),
    apt_number VARCHAR(255),
    bathroom_count VARCHAR(255),
    bedroom_count VARCHAR(255),
    room_count VARCHAR(255),
    qn6j_building_id VARCHAR(255),
    PRIMARY KEY (apt_id),
    FOREIGN KEY (qn6j_building_id) REFERENCES Apartment_Buildings(building_id)
);

CREATE TABLE Apartment_Facilities (
    facility_code VARCHAR(255),
    vxf8_apt_id VARCHAR(255),
    PRIMARY KEY (apt_id, facility_code),
    FOREIGN KEY (vxf8_apt_id) REFERENCES Apartments(apt_id)
);

CREATE TABLE Guests (
    guest_id VARCHAR(255),
    gender_code VARCHAR(255),
    guest_first_name VARCHAR(255),
    guest_last_name VARCHAR(255),
    date_of_birth VARCHAR(255),
    PRIMARY KEY (guest_id)
);

-- Added FK to Guests because Apartment_Bookings is the many side.
-- Added FK to Apartments because Apartment_Bookings is the many side.

CREATE TABLE Apartment_Bookings (
    apt_booking_id VARCHAR(255),
    booking_status_code VARCHAR(255),
    booking_start_date VARCHAR(255),
    booking_end_date VARCHAR(255),
    hstg_guest_id VARCHAR(255),
    akpx_apt_id VARCHAR(255),
    PRIMARY KEY (apt_booking_id),
    FOREIGN KEY (hstg_guest_id) REFERENCES Guests(guest_id),
    FOREIGN KEY (akpx_apt_id) REFERENCES Apartments(apt_id)
);

-- Added FK to Apartment_Bookings because View_Unit_Status is the many side.
-- Added FK to Apartments because View_Unit_Status is the many side.

CREATE TABLE View_Unit_Status (
    status_date VARCHAR(255),
    available_yn VARCHAR(255),
    uoe2_apt_booking_id VARCHAR(255),
    p7al_apt_id VARCHAR(255),
    PRIMARY KEY (status_date),
    FOREIGN KEY (uoe2_apt_booking_id) REFERENCES Apartment_Bookings(apt_booking_id),
    FOREIGN KEY (p7al_apt_id) REFERENCES Apartments(apt_id)
);
    """

    schema2 = """
CREATE TABLE Apartment_Buildings (
building_id INTEGER NOT NULL,
building_short_name CHAR(15),
building_full_name VARCHAR(80),
building_description VARCHAR(255),
building_address VARCHAR(255),
building_manager VARCHAR(50),
building_phone VARCHAR(80),
PRIMARY KEY (building_id),
UNIQUE (building_id)
);

CREATE TABLE Apartments (
apt_id INTEGER NOT NULL ,
building_id INTEGER NOT NULL,
apt_type_code CHAR(15),
apt_number CHAR(10),
bathroom_count INTEGER,
bedroom_count INTEGER,
room_count CHAR(5),
PRIMARY KEY (apt_id),
UNIQUE (apt_id),
FOREIGN KEY (building_id) REFERENCES Apartment_Buildings (building_id)
);

CREATE TABLE Apartment_Facilities (
apt_id INTEGER NOT NULL,
facility_code CHAR(15) NOT NULL,
PRIMARY KEY (apt_id, facility_code),
FOREIGN KEY (apt_id) REFERENCES Apartments (apt_id)
);

CREATE TABLE Guests (
guest_id INTEGER NOT NULL ,
gender_code CHAR(1),
guest_first_name VARCHAR(80),
guest_last_name VARCHAR(80),
date_of_birth DATETIME,
PRIMARY KEY (guest_id),
UNIQUE (guest_id)
);

CREATE TABLE Apartment_Bookings (
apt_booking_id INTEGER NOT NULL,
apt_id INTEGER,
guest_id INTEGER NOT NULL,
booking_status_code CHAR(15) NOT NULL,
booking_start_date DATETIME,
booking_end_date DATETIME,
PRIMARY KEY (apt_booking_id),
UNIQUE (apt_booking_id),
FOREIGN KEY (apt_id) REFERENCES Apartments (apt_id),
FOREIGN KEY (guest_id) REFERENCES Guests (guest_id)
);

CREATE TABLE View_Unit_Status (
apt_id INTEGER,
apt_booking_id INTEGER,
status_date DATETIME NOT NULL,
available_yn BIT,
PRIMARY KEY (status_date),
FOREIGN KEY (apt_id) REFERENCES Apartments (apt_id),
FOREIGN KEY (apt_booking_id) REFERENCES Apartment_Bookings (apt_booking_id)
);
    """

    diff, equivalent = compare_schemas(schema1, schema2)

    if equivalent:
        print("Schemas are equivalent")
    else:
        for line in diff:
            print(line)

    """    file_path = "../ERDtoSQL Test/UMLTestsCardinality"

    equivalent_groups = []  # list of groups

    for dirpath, dirnames, filenames in os.walk(file_path):
        for filename in filenames:
            if filename.endswith(".sql"):
                with open(os.path.join(dirpath, filename), "r") as f:
                    sql = f.read()

                found_equivalent = False

                # check this SQL against existing groups
                for group in equivalent_groups:
                    representative_sql = group["files"][0]["sql"]  # baseline = first file in group
                    diff, equivalent = compare_schemas(sql, representative_sql)
                    if equivalent:
                        group["files"].append({
                            "filename": filename,
                            "sql": sql
                        })
                        found_equivalent = True
                        break

                # if not equivalent to any existing group, make a new one
                if not found_equivalent:
                    equivalent_groups.append({
                        "files": [
                            {
                                "filename": filename,
                                "sql": sql
                            }
                        ]
                    })

    # print results
    for idx, group in enumerate(equivalent_groups, 1):
        print(f"\nGroup {idx}:")
        for f in group["files"]:
            print("  -", f["filename"])"""

