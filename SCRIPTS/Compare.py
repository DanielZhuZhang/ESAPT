from sqlglot.expressions import (
    Create, ColumnDef, Constraint, PrimaryKey,
    ForeignKey, PrimaryKeyColumnConstraint
)
import os
from sqlglot import parse, exp


import re

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

def compare_attributes(expr, expr2):
    attributes1 = [col.this.this for col in expr.find_all(ColumnDef)]
    attributes2 = [col.this.this for col in expr2.find_all(ColumnDef)]

    only_in_1 = set(attributes1) - set(attributes2)
    only_in_2 = set(attributes2) - set(attributes1)

    results = []
    equivalent = True

    if only_in_1:
        results.append("only in schema1: " + str(only_in_1))
        equivalent = False
    if only_in_2:
        results.append("only in schema2: " + str(only_in_2))
        equivalent = False

    return results, equivalent


def primary_key_checker(expr1, expr2):
    pk1 = []
    pk2 = []

    # schema 1
    for col in expr1.this.expressions:
        if col.args.get("constraints"):
            for cons in col.args["constraints"]:
                if isinstance(cons.kind, PrimaryKeyColumnConstraint):
                    pk1.append(col.name)
    for expr in expr1.this.expressions:
        if isinstance(expr, PrimaryKey):
            for pk in expr.expressions:
                pk1.append(pk.this)

    # schema 2
    for col in expr2.this.expressions:
        if col.args.get("constraints"):
            for cons in col.args["constraints"]:
                if isinstance(cons.kind, PrimaryKeyColumnConstraint):
                    pk2.append(col.name)
    for expr in expr2.this.expressions:
        if isinstance(expr, PrimaryKey):
            for pk in expr.expressions:
                pk2.append(pk.this)

    if set(pk1) == set(pk2):
        return ["Primary keys are the same"], True
    else:
        return [f"Primary key mismatch:\n  schema1: {pk1}\n  schema2: {pk2}"], False


def foreign_key_checker(expr1, expr2):
    def extract_fk(expr):
        fks = []
        for e in expr.this.expressions:
            if isinstance(e, Constraint):
                for constraint in e.expressions:
                    if isinstance(constraint, ForeignKey):
                        reference = constraint.args.get("reference")
                        fk = [reference.this.this.this.this]
                        for iden in reference.this.expressions:
                            fk.append(iden.this)
                        fks.append(fk)
            elif isinstance(e, ForeignKey):
                reference = e.args.get("reference")
                fk = [reference.this.this.this.this]
                for iden in reference.this.expressions:
                    fk.append(iden.this)
                fks.append(fk)
        return fks

    fk1 = extract_fk(expr1)
    fk2 = extract_fk(expr2)

    if set(tuple(fk) for fk in fk1) == set(tuple(fk) for fk in fk2):
        return ["Foreign keys are the same"], True
    else:
        return [f"Foreign key differences:\n  schema1: {fk1}\n  schema2: {fk2}"], False


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


    # columns present in both schemas
    for col in set(cons1.keys()) | set(cons2.keys()):
        c1 = cons1.get(col, set())
        c2 = cons2.get(col, set())
        if c1 != c2:
            results.append(f"Constraint mismatch on column '{col}':\n  schema1: {c1}\n  schema2: {c2}")
            equivalent = False

    return results, equivalent

def compare_schemas(schema1_str, schema2_str):
    schema1_str, schema2_str = clean_sql(extract_create_tables(schema1_str)), clean_sql(extract_create_tables(schema2_str))
    equivalent = True
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
        equivalent = False
    if only_in_2:
        results.append(f"Tables only in schema2: {only_in_2}")
        equivalent = False
    if not common_tables:
        results.append("No common tables to compare.")
        return results, False


    for table in common_tables:
        results.append(f"\nComparing table: {table}")

        table_clean_1 = get_create_node_for_table(ast1_clean, table)
        table_clean_2 = get_create_node_for_table(ast2_clean, table)

        table_orig_1 = get_create_node_for_table(ast1, table)
        table_orig_2 = get_create_node_for_table(ast2, table)

        # attributes
        attr_diff, attrs_eq = compare_attributes(table_clean_1, table_clean_2)
        if not attrs_eq:
            equivalent = False
            results.extend(attr_diff)
        # primary keys
        pk_diff, pk_eq = primary_key_checker(table_orig_1, table_orig_2)
        if not pk_eq:
            equivalent = False
            results.extend(pk_diff)

        # foreign keys
        fk_diff, fk_eq = foreign_key_checker(table_orig_1, table_orig_2)
        if not fk_eq:
            equivalent = False
            results.extend(fk_diff)
        if equivalent:
            results = []

    return results, equivalent


if __name__ == "__main__":
    schema1 = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name TEXT
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

INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (133, 'Normandie Court', 'Normandie Court', 'Studio', '7950 Casper Vista Apt. 176
Marquiseberg, CA 70496', 'Emma', '(948)040-1064x387');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (153, 'Mercedes House', 'Mercedes House', 'Studio', '354 Otto Villages
Charliefort, VT 71664', 'Brenden', '915-617-2408x832');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (191, 'The Eugene', 'The Eugene', 'Flat', '71537 Gorczany Inlet
Wisozkburgh, AL 08256', 'Melyssa', '(609)946-0491');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (196, 'VIA 57 WEST', 'VIA 57 WEST', 'Studio', '959 Ethel Viaduct
West Efrainburgh, DE 40074', 'Kathlyn', '681.772.2454');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (225, 'Columbus Square', 'Columbus Square', 'Studio', '0703 Danika Mountains Apt. 362
Mohrland, AL 56839-5028', 'Kyle', '1-724-982-9507x640');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (532, 'Avalon Park', 'Avalon Park', 'Duplex', '6827 Kessler Parkway Suite 908
Ahmedberg, WI 48788', 'Albert', '376-017-3538');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (556, 'Peter Cooper Village', 'Peter Cooper Village', 'Flat', '861 Narciso Glens Suite 392
East Ottis, ND 73970', 'Darlene', '1-224-619-0295x13195');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (624, 'Stuyvesant Town', 'Stuyvesant Town', 'Studio', '101 Queenie Mountains Suite 619
New Korbinmouth, KS 88726-1376', 'Marie', '(145)411-6406');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (644, 'The Anthem', 'The Anthem', 'Flat', '50804 Mason Isle Suite 844
West Whitney, ID 66511', 'Ewald', '(909)086-5221x3455');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (673, 'Barclay Tower', 'Barclay Tower', 'Flat', '1579 Runte Forges Apt. 548
Leuschkeland, OK 12009-8683', 'Rogers', '1-326-267-3386x613');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (734, 'Windsor Court', 'Windsor Court', 'Studio', '601 Graham Roads
Port Luz, VA 29660-6703', 'Olaf', '(480)480-7401');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (744, 'Silver Towers', 'Silver Towers', 'Flat', '1844 Armstrong Stravenue Suite 853
Myrnatown, CT 13528', 'Claude', '1-667-728-2287x3158');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (790, 'Biltmore Plaza', 'Biltmore Plaza', 'Duplex', '489 Josh Orchard Apt. 998
Sipesview, DE 69053', 'Sydni', '544-148-5565x2847');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (808, 'Petersfield', 'Petersfield', 'Studio', '54686 Christopher Circles Apt. 321
Daytonland, ID 88081-3991', 'Juvenal', '318-398-8140');
INSERT INTO `Apartment_Buildings` (`building_id`, `building_short_name`, `building_full_name`, `building_description`, `building_address`, `building_manager`, `building_phone`) VALUES (968, 'The Clinton', 'The Clinton', 'Flat', '012 Arnoldo Mountain
Gerholdland, ID 23342', 'Holly', '1-605-511-1973x25011');

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
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (1, 808, 'Flat', 'Suite 645', 1, 3, '7');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (2, 624, 'Flat', 'Apt. 585', 2, 4, '5');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (3, 225, 'Studio', 'Apt. 908', 1, 6, '7');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (4, 225, 'Duplex', 'Suite 749', 1, 5, '8');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (5, 744, 'Flat', 'Suite 307', 2, 4, '9');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (6, 191, 'Studio', 'Apt. 187', 3, 5, '9');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (7, 790, 'Studio', 'Suite 088', 2, 4, '6');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (8, 153, 'Flat', 'Suite 693', 2, 3, '9');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (9, 624, 'Studio', 'Apt. 940', 1, 4, '8');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (10, 225, 'Duplex', 'Apt. 859', 2, 3, '6');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (11, 734, 'Flat', 'Apt. 794', 1, 5, '3');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (12, 673, 'Duplex', 'Apt. 477', 2, 6, '3');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (13, 744, 'Duplex', 'Apt. 411', 2, 5, '9');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (14, 225, 'Flat', 'Apt. 837', 2, 4, '8');
INSERT INTO `Apartments` (`apt_id`, `building_id`, `apt_type_code`, `apt_number`, `bathroom_count`, `bedroom_count`, `room_count`) VALUES (15, 790, 'Duplex', 'Suite 634', 3, 6, '8');

CREATE TABLE Apartment_Facilities (
apt_id INTEGER NOT NULL,
facility_code CHAR(15) NOT NULL,
PRIMARY KEY (apt_id, facility_code),
FOREIGN KEY (apt_id) REFERENCES Apartments (apt_id)
);
INSERT INTO `Apartment_Facilities` (`apt_id`, `facility_code`) VALUES (1, 'Boardband');
INSERT INTO `Apartment_Facilities` (`apt_id`, `facility_code`) VALUES (2, 'Boardband');
INSERT INTO `Apartment_Facilities` (`apt_id`, `facility_code`) VALUES (3, 'Gym');
INSERT INTO `Apartment_Facilities` (`apt_id`, `facility_code`) VALUES (5, 'Swimming Pool');
INSERT INTO `Apartment_Facilities` (`apt_id`, `facility_code`) VALUES (6, 'Cable TV');
INSERT INTO `Apartment_Facilities` (`apt_id`, `facility_code`) VALUES (9, 'Boardband');
INSERT INTO `Apartment_Facilities` (`apt_id`, `facility_code`) VALUES (15, 'Gym');
CREATE TABLE Guests (
guest_id INTEGER NOT NULL ,
gender_code CHAR(1),
guest_first_name VARCHAR(80),
guest_last_name VARCHAR(80),
date_of_birth DATETIME,
PRIMARY KEY (guest_id),
UNIQUE (guest_id)
);

INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (1, 'Male', 'Kip', 'DuBuque', '1995-11-04 07:09:57');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (2, 'Unknown', 'Rebeca', 'Runolfsdottir', '1974-05-12 21:53:58');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (3, 'Female', 'Keon', 'Treutel', '1974-08-20 09:28:05');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (4, 'Female', 'Gabe', 'Bode', '2007-09-11 19:01:39');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (5, 'Female', 'Lou', 'Grady', '1997-01-15 17:37:40');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (6, 'Unknown', 'Josefina', 'Jerde', '1978-03-08 04:43:04');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (7, 'Female', 'Mozell', 'Toy', '1997-01-20 17:11:31');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (8, 'Unknown', 'Keith', 'Hoeger', '2001-06-18 20:05:55');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (9, 'Female', 'Crystal', 'Runolfsson', '1971-01-04 04:22:58');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (10, 'Female', 'Nikki', 'Lehner', '1980-06-20 18:15:39');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (11, 'Male', 'Gregoria', 'Schowalter', '2015-02-03 23:34:13');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (12, 'Male', 'Louvenia', 'Crona', '1983-08-26 15:45:08');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (13, 'Female', 'Else', 'Roberts', '1971-11-02 01:51:56');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (14, 'Female', 'Juvenal', 'Kautzer', '2003-07-29 22:08:15');
INSERT INTO `Guests` (`guest_id`, `gender_code`, `guest_first_name`, `guest_last_name`, `date_of_birth`) VALUES (15, 'Female', 'Tamia', 'Mante', '2013-02-22 11:26:22');


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
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (258, 10, 2, 'Provisional', '2016-09-26 17:13:49', '2017-10-07 11:38:48');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (279, 15, 15, 'Provisional', '2016-04-01 06:28:08', '2017-10-25 11:08:42');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (337, 8, 5, 'Provisional', '2017-03-13 16:20:14', '2018-02-19 16:59:08');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (343, 4, 13, 'Confirmed', '2016-08-04 10:33:00', '2017-09-29 12:43:50');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (365, 9, 12, 'Confirmed', '2017-02-11 14:34:14', '2017-10-07 20:47:19');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (401, 7, 14, 'Provisional', '2016-05-24 20:09:38', '2017-10-03 01:56:21');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (497, 10, 8, 'Confirmed', '2016-07-25 02:57:04', '2017-09-28 11:08:15');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (526, 8, 7, 'Confirmed', '2016-11-26 05:04:31', '2018-02-25 15:15:37');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (575, 6, 3, 'Provisional', '2017-05-13 18:17:20', '2017-10-06 11:15:58');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (577, 12, 2, 'Provisional', '2017-03-04 02:23:49', '2018-02-06 16:57:05');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (623, 4, 5, 'Provisional', '2016-06-07 05:05:18', '2017-11-13 13:59:45');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (807, 11, 2, 'Provisional', '2016-04-17 12:53:59', '2018-03-20 17:32:58');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (889, 10, 4, 'Confirmed', '2016-09-28 05:00:50', '2017-09-30 18:41:04');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (920, 2, 2, 'Confirmed', '2017-04-07 04:53:27', '2017-11-29 12:59:42');
INSERT INTO `Apartment_Bookings` (`apt_booking_id`, `apt_id`, `guest_id`, `booking_status_code`, `booking_start_date`, `booking_end_date`) VALUES (924, 8, 3, 'Confirmed', '2017-07-03 14:15:56', '2017-11-12 01:05:09');

INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (11, 920, '1970-09-28 10:24:29', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (15, 575, '1972-03-23 22:55:53', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (15, 924, '1973-10-28 04:30:14', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (6, 497, '1976-12-18 04:03:51', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (12, 807, '1977-04-15 13:42:19', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (13, 575, '1978-12-28 11:53:34', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (2, 497, '1980-11-12 13:34:45', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (14, 401, '1985-11-05 11:46:35', '0');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (11, 497, '1990-11-04 17:57:50', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (13, 337, '2000-02-04 07:50:09', '0');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (14, 279, '2001-02-17 20:17:09', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (5, 337, '2003-07-25 10:13:48', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (1, 497, '2003-08-02 08:36:36', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (10, 497, '2006-02-23 05:50:04', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (6, 401, '2011-02-12 09:04:07', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (9, 623, '2011-11-06 22:08:42', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (14, 920, '2012-11-24 13:39:37', '0');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (4, 258, '2014-12-10 13:53:21', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (13, 343, '2015-06-19 07:59:01', '1');
INSERT INTO `View_Unit_Status` (`apt_id`, `apt_booking_id`, `status_date`, `available_yn`) VALUES (5, 889, '2015-07-15 11:06:29', '1');
    """

    diff, equivalent = compare_schemas(schema1, schema2)

    if equivalent:
        print("Schemas are equivalent")
    else:
        for line in diff:
            print(line)

    file_path = "../ERDtoSQL Test/UMLTestsCardinality"

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
            print("  -", f["filename"])

