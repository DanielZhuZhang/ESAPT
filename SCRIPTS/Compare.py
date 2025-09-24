from sqlglot import parse
from sqlglot.expressions import (
    Create, ColumnDef, Constraint, PrimaryKey,
    ForeignKey, PrimaryKeyColumnConstraint
)
import os


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

def constraint_checker(expr1, expr2):
    def extract_constraints(expr):
        constraints = {}
        for col in expr.this.expressions:
            if hasattr(col, "args") and col.args.get("constraints"):
                col_constraints = []
                for cons in col.args["constraints"]:
                    # normalize constraint type
                    if cons.this:
                        col_constraints.append(cons.this.upper())
                    if cons.kind:
                        col_constraints.append(cons.kind.__class__.__name__.upper())
                constraints[col.name] = set(col_constraints)
        return constraints

    cons1 = extract_constraints(expr1)
    cons2 = extract_constraints(expr2)

    results = []
    equivalent = True

    # columns present in both schemas
    for col in set(cons1.keys()) | set(cons2.keys()):
        c1 = cons1.get(col, set())
        c2 = cons2.get(col, set())
        if c1 != c2:
            results.append(f"Constraint mismatch on column '{col}':\n  schema1: {c1}\n  schema2: {c2}")
            equivalent = False

    return results, equivalent

def compare_schemas(schema1_str, schema2_str):
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
        results.extend(attr_diff)
        if not attrs_eq:
            equivalent = False
        cons_diff, cons_eq = constraint_checker(table_orig_1, table_orig_2)
        results.extend(cons_diff)
        if not cons_eq:
            equivalent = False
        # primary keys
        pk_diff, pk_eq = primary_key_checker(table_orig_1, table_orig_2)
        results.extend(pk_diff)
        if not pk_eq:
            equivalent = False

        # foreign keys
        fk_diff, fk_eq = foreign_key_checker(table_orig_1, table_orig_2)
        results.extend(fk_diff)
        if not fk_eq:
            equivalent = False

    return results, equivalent


if __name__ == "__main__":
    schema1 = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name TEXT
    );
    """

    schema2 = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name TEXT
    );
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

