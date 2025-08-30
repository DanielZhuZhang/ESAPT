import os
import sqlite3
import pandas as pd

def delete_if_exists(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)
        print("Deleted file")

def extract_schema(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]

    tables_list = []
    foreign_keys_summary = []

    tables_without_primary_key = []
    outgoing_relations = set()
    incoming_relations = set()

    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        has_primary_key = False

        for col in columns:
            if col[5] > 0:
                has_primary_key = True
            tables_list.append({
                'table_name': table,
                'column_id': col[0],
                'column_name': col[1],
                'data_type': col[2],
                'not_null': bool(col[3]),
                'default_value': col[4],
                'is_primary_key': bool(col[5])
            })

        if not has_primary_key:
            tables_without_primary_key.append(table)

        cursor.execute(f"PRAGMA foreign_key_list({table})")
        fks = cursor.fetchall()
        for fk in fks:
            foreign_keys_summary.append({
                'table_name': table,
                'from_column': fk[3],
                'ref_table': fk[2],
                'ref_column': fk[4],
                'on_update': fk[5],
                'on_delete': fk[6]
            })

            outgoing_relations.add(table)
            incoming_relations.add(fk[2])

    conn.close()

    related_tables = outgoing_relations.union(incoming_relations)
    tables_without_relations = [t for t in tables if t not in related_tables]

    # Convert to DataFrame
    schema_df = pd.DataFrame(tables_list)
    foreign_keys_df = pd.DataFrame(foreign_keys_summary)

    return schema_df, foreign_keys_df, tables_without_primary_key, tables_without_relations

def write_anomalies_report(folder, no_pk_tables, no_relation_tables, db_filename):
    anomaly_path = os.path.join(folder, f"{os.path.splitext(db_filename)[0]}_anomalies.txt")
    delete_if_exists(anomaly_path)

    if no_pk_tables or no_relation_tables:
        with open(anomaly_path, "w") as f:
            f.write("Anomalies Detected:\n")

            if no_pk_tables:
                f.write("\nTables with no Primary Key:\n")
                for table in no_pk_tables:
                    f.write(f"- {table}\n")

            if no_relation_tables:
                f.write("\nTables with no Relationships (not linked by any FK):\n")
                for table in no_relation_tables:
                    f.write(f"- {table}\n")

        print(f"Anomaly report written to: {anomaly_path}")
    else:
        print(f"No anomalies found in {db_filename}.")

def process_all_sqlite_files(directory):
    total_files = 0
    total_tables_scanned = 0
    total_anomalous_tables = 0
    total_files_with_anomalies = 0

    for foldername, subfolders, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith(".sqlite"):
                file_path = os.path.join(foldername, filename)
                print(f"\nProcessing {file_path}")
                total_files += 1

                schema_df, fk_df, tables_without_pk, tables_without_rel = extract_schema(file_path)

                # Count total tables in this DB
                db_table_names = schema_df['table_name'].unique()
                total_tables_scanned += len(db_table_names)

                # Count unique anomalous tables in this DB
                anomalous_tables = set(tables_without_pk).union(tables_without_rel)
                num_anomalous = len(anomalous_tables)
                total_anomalous_tables += num_anomalous

                if num_anomalous > 0:
                    total_files_with_anomalies += 1

                write_anomalies_report(foldername, tables_without_pk, tables_without_rel, filename)

    # Final Summary
    print(f"Total .sqlite files processed         : {total_files}")
    print(f"Total tables scanned                  : {total_tables_scanned}")
    print(f"Total tables with anomalies           : {total_anomalous_tables}")
    print(f"Total .sqlite files with anomalies    : {total_files_with_anomalies}")




if __name__ == '__main__':
    # db_path = '../customer_deliveries.sqlite'  # Replace with your SQLite file path
    # schema_df, foreign_keys_df, tables_without_primary_key = extract_schema(db_path)
    #
    # # Save to CSVs
    # schema_df.to_csv('FilterOutput/schema_columns.csv', index=False)
    # foreign_keys_df.to_csv('FilterOutput/foreign_keys.csv', index=False)
    #
    # print("=== Schema ===")
    # print(schema_df)
    # print("\n=== Foreign Keys ===")
    # print(foreign_keys_df)
    # print("\n=== Tables without Primary Key ===")
    # print(tables_without_primary_key)
    #
    root_dir = "Spider Dataset2"
    process_all_sqlite_files(root_dir)
