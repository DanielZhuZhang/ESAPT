import re
from sqlglot import parse

def extract_create_tables(sql_text):
    return "\n".join(
        re.findall(r"CREATE TABLE.*?;", sql_text, flags=re.DOTALL | re.IGNORECASE)
    )

def check_file(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    schema_only = extract_create_tables(content)
    try:
        parse(schema_only)
        return None  # no error
    except Exception as e:
        return str(e)

import os

directory = "../Spider Dataset(Clean)/Daniel"
errors = []

for dirpath, _, filenames in os.walk(directory):
    for filename in filenames:
        if filename.endswith(".sql"):
            file_path = os.path.join(dirpath, filename)
            err = check_file(file_path)
            if err:
                errors.append((file_path, err))

for f, e in errors:
    print(f"{f}: {e}")
