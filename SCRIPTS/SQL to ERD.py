import sqlite3
import os
import pandas as pd

schema = ("""
-- Drop tables if they exist (for testing)
DROP TABLE IF EXISTS Enrollment;
DROP TABLE IF EXISTS Student;
DROP TABLE IF EXISTS Course;
DROP TABLE IF EXISTS Department;
DROP TABLE IF EXISTS Building;
DROP TABLE IF EXISTS Classroom;
DROP TABLE IF EXISTS ClubMembership;
DROP TABLE IF EXISTS Club;
DROP TABLE IF EXISTS Event;
DROP TABLE IF EXISTS EventParticipation;
DROP TABLE IF EXISTS StudentIDCard ;

-----------------------------------------------------
-- MANY-TO-ONE RELATIONSHIP (Students -> Department)
-----------------------------------------------------
CREATE TABLE Department (
    department_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE Student (
    student_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department_id INT,
    FOREIGN KEY (department_id) REFERENCES Department(department_id)
);

-----------------------------------------------------
-- ONE-TO-ONE RELATIONSHIP (Student <-> StudentIDCard)
-----------------------------------------------------
CREATE TABLE StudentIDCard (
    student_id INT PRIMARY KEY,
    card_number VARCHAR(20) UNIQUE NOT NULL,
    issue_date DATE,
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-----------------------------------------------------
-- MANY-TO-MANY RELATIONSHIP (Students <-> Courses)
-----------------------------------------------------
CREATE TABLE Course (
    course_id INT PRIMARY KEY,
    course_name VARCHAR(100) NOT NULL,
    department_id INT,
    FOREIGN KEY (department_id) REFERENCES Department(department_id)
);

-- Enrollment is the bridge table (weak entity, since PK depends on Student+Course)
CREATE TABLE Enrollment (
    student_id INT,
    course_id INT,
    grade CHAR(2),
    PRIMARY KEY (student_id, course_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (course_id) REFERENCES Course(course_id)
);

-----------------------------------------------------
-- WEAK ENTITY (Classroom depends on Building)
-----------------------------------------------------
CREATE TABLE Building (
    building_id INT PRIMARY KEY,
    building_name VARCHAR(100) NOT NULL
);

-- Classroom is a weak entity: identified by building_id + room_number
CREATE TABLE Classroom (
    building_id INT,
    room_number VARCHAR(10),
    capacity INT,
    PRIMARY KEY (building_id, room_number),
    FOREIGN KEY (building_id) REFERENCES Building(building_id)
);

-----------------------------------------------------
-- MANY-TO-MANY RELATIONSHIP WITH EXTRA ATTRIBUTES
-- (Clubs <-> Students, includes role attribute)
-----------------------------------------------------
CREATE TABLE Club (
    club_id INT PRIMARY KEY,
    club_name VARCHAR(100) NOT NULL
);

CREATE TABLE ClubMembership (
    student_id INT,
    club_id INT,
    role VARCHAR(50),
    PRIMARY KEY (student_id, club_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (club_id) REFERENCES Club(club_id)
);

-----------------------------------------------------
-- ANOTHER MANY-TO-MANY (Events <-> Students)
-----------------------------------------------------
CREATE TABLE Event (
    event_id INT PRIMARY KEY,
    event_name VARCHAR(100) NOT NULL,
    event_date DATE
);

CREATE TABLE EventParticipation (
    event_id INT,
    student_id INT,
    feedback TEXT,
    PRIMARY KEY (event_id, student_id),
    FOREIGN KEY (event_id) REFERENCES Event(event_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-- Departments
INSERT INTO Department VALUES (1, 'Computer Science');
INSERT INTO Department VALUES (2, 'Mathematics');

-- Students
INSERT INTO Student VALUES (101, 'Alice', 1);
INSERT INTO Student VALUES (102, 'Bob', 2);

-- Courses
INSERT INTO Course VALUES (201, 'Databases', 1);
INSERT INTO Course VALUES (202, 'Linear Algebra', 2);

-- Enrollment (many-to-many)
INSERT INTO Enrollment VALUES (101, 201, 'A');
INSERT INTO Enrollment VALUES (102, 202, 'B');

-- Buildings & Classrooms
INSERT INTO Building VALUES (1, 'Science Hall');
INSERT INTO Classroom VALUES (1, '101', 40);

-- Clubs & Memberships
INSERT INTO Club VALUES (301, 'Chess Club');
INSERT INTO ClubMembership VALUES (101, 301, 'President');

-- Events & Participation
INSERT INTO Event VALUES (401, 'Math Conference', '2025-09-13');
INSERT INTO EventParticipation VALUES (401, 102, 'Great event!');
""")

def sql_to_sqlite(schema, file_path):
    conn = sqlite3.connect(file_path)
    cursor = conn.cursor()

    cursor.executescript(schema)

    conn.commit()
    conn.close()

def analyze_sqlite_schema(sqlite_file):
    conn = sqlite3.connect(sqlite_file)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    table_names = [row[0] for row in cursor.fetchall()]

    schema_dict = {}

    for table in table_names:

        # Foreign Keys
        cursor.execute(f"PRAGMA foreign_key_list('{table}')")
        fks = cursor.fetchall()
        if len(fks) > 0:
          fk_df = pd.DataFrame(fks, columns=[
              "id", "seq", "ref_table", "from_col", "to_col", "on_update", "on_delete", "match"
          ])
        else:
          fk_df = pd.DataFrame(columns=[
              "id", "seq", "ref_table", "from_col", "to_col", "on_update", "on_delete", "match"
          ])


        # Columns
        cursor.execute(f"PRAGMA table_info('{table}')")
        cols = cursor.fetchall()
        col_df = pd.DataFrame(cols, columns=["cid", "name", "type", "notnull", "dflt_value", "pk"])

        # UNIQUE constraints
        cursor.execute(f"PRAGMA index_list('{table}')")
        indexes = cursor.fetchall()

        unique_cols = []
        for idx in indexes:
            idx_name = idx[1]
            is_unique = bool(idx[2]) #Find Unique Constraint
            if is_unique:
                cursor.execute(f"PRAGMA index_info('{idx_name}')")
                idx_cols = cursor.fetchall()
                for c in idx_cols:
                    unique_cols.append(c[2]) # Find Column Name

        col_df["is_unique"] = col_df["name"].apply(lambda x: x in unique_cols)

        schema_dict[table] = {
            "columns": col_df,
            "foreign_keys": fk_df
        }

    conn.close()
    return schema_dict
if __name__ == "__main__":
    os.makedirs("Test Files", exist_ok=True)
    sqlite_file = "Test Files/mydb.sqlite"
    sql_to_sqlite(schema, sqlite_file)
    schema_dict = analyze_sqlite_schema(sqlite_file)

    for table, info in schema_dict.items():
        print("=" * 60)
        print(f" Table: {table}")

        print("\nColumns:")
        print(info['columns'].to_string(index=False))

        print("\nForeign Keys:")
        if info['foreign_keys'].empty:
            print("None")
        else:
            print(info['foreign_keys'].to_string(index=False))

        print("\n")
    tables = {}
    for table, info in schema_dict.items():
        col_df = info["columns"]
        fk_df = info["foreign_keys"]

        is_pk = set(col_df.loc[col_df["pk"] > 0, "name"])
        is_fk = set(fk_df["from_col"])
        is_unique = set(col_df.loc[col_df["is_unique"] == True, "name"])

        if is_pk == is_fk and len(is_pk) > 0:
            tables[table] = {"type": "Associative"}
        elif (len(is_pk & is_fk) > 0) and (len(is_pk - is_fk) > 0):
            tables[table] = {"type": "Weak Entity"}
        else:
            tables[table] = {"type": "Entity"}
    print(tables)
    print(fk_df)
    for _, fk in fk_df.iterrows():
        from_col = fk["from_col"]
        to_table = fk["ref_table"]
        to_col = fk["to_col"]

        if from_col in is_unique:
            relation_type = "1:1"
        else:
            relation_type = "1:N"