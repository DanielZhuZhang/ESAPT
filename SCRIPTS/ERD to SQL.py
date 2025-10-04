import xml.etree.ElementTree as ET
import os

SHAPE_MAP = {}
RELATIONSHIPS = {}

#Chen or Crow's Foot or UML
CURRENT_NOTATION = "UML"

style_hashmap = {
    "Chen(Simple)":{
        "Optional: 0 or 1": {
            "value": "1"
        },
        "0 or More": {
            "value": "N"
        },
    },
    "Chen": {
        "Exactly 1": {
            "end_style": "endArrow=open;endFill=0",
            "start_style": "startArrow=open;startFill=0",
        },
        "Optional: 0 or 1": {
            "end_style": "endArrow=block;endFill=1",
            "start_style": "startArrow=block;startFill=1",
        },
        "1 or More": {
            "value": "1..*"
        }
    },
    "Crow's Foot": {
        "Exactly 1": {
            "end_style": "endArrow=ERmandOne;endFill=0",
            "start_style": "startArrow=ERmandOne;startFill=0",
        },
        "Optional: 0 or 1": {
            "end_style": "endArrow=ERzeroToOne;endFill=0",
            "start_style": "startArrow=ERzeroToOne;startFill=0",
        },
        "0 or More": {
            "end_style": "endArrow=ERoneToMany;endFill=0",
            "start_style": "startArrow=ERoneToMany;startFill=0",
        },
        "1 or More": {
            "end_style": "endArrow=ERmany;endFill=0",
            "start_style": "startArrow=ERmany;startFill=0",
        }
    },
    "UML": {
        "Exactly 1": {
            "value": "1"
        },
        "Optional: 0 or 1": {
            "value": "0..1"
        },
        "0 or More": {
            "value": "*"
        },
        "1 or More": {
            "value": ("5..10","1..*")
        }
    }
}

def check_cardinality(style, value):
    for cardinality, cardinality_mapping in style_hashmap[CURRENT_NOTATION].items():
        if "value" in cardinality_mapping:
            mapping_value = cardinality_mapping["value"]

            if isinstance(mapping_value, tuple):
                if value in mapping_value:
                    return cardinality
            else:
                if value == mapping_value:
                    return cardinality

        elif "end_style" in cardinality_mapping:
            if (cardinality_mapping.get("end_style") in style or
                cardinality_mapping.get("start_style") in style):
                return cardinality

    # notation fallbacks
    if CURRENT_NOTATION == "Chen" and "endArrow=none;endFill=0;startArrow=none;startFill=0;" in style:
        return "0 or More"
    if CURRENT_NOTATION == "Chen" and ("endArrow=blockThin;" in style or "startArrow=blockThin;" in style):
        return "Optional: 0 or 1"
    if CURRENT_NOTATION == "Chen":
        if "endArrow=none;endFill=0" in style and "startArrow=" not in style:
            return "0 or More"
        if "startArrow=none;startFill=0" in style and "endArrow=" not in style:
            return "0 or More"

    return None


def print_dict(d, indent=0):
    spacing = "  " * indent
    if isinstance(d, dict):
        for key, value in d.items():
            if isinstance(value, (dict, list)):
                print(f"{spacing}{key}:")
                print_dict(value, indent + 1)
            else:
                print(f"{spacing}{key}: {value}")
    elif isinstance(d, list):
        for i, item in enumerate(d):
            print(f"{spacing}- [{i}]")
            print_dict(item, indent + 1)
    else:
        print(f"{spacing}{d}")


import html

def update_shape_map(tree):
    for cell in tree.iter("mxCell"):
        style = cell.get("style", "")
        id = cell.get("id", "")
        value = html.unescape(cell.get("value", "").strip())

        if "shape=rectangle;" in style or "shape=ext" in style or (style == "whiteSpace=wrap;html=1;align=center;"):
            if "double=1" in style:
                SHAPE_MAP[id] = {
                    "Type": "Entity",
                    "Weak": True,
                    "Name": value,
                    "Attributes": []
                }
            else:
                SHAPE_MAP[id] = {
                    "Type": "Entity",
                    "Weak": False,
                    "Name": value,
                    "Attributes": []
                }

        elif "rhombus" in style:
            if "double=1" in style:
                SHAPE_MAP[id] = {
                    "Type": "RELATION",
                    "Name": value,
                    "Weak": True,
                    "Attributes": []
                }
            else:
                SHAPE_MAP[id] = {
                    "Type": "RELATION",
                    "Name": value,
                    "Weak": False,
                    "Attributes": []
                }


        elif "ellipse" in style:
            is_pk = ("fontStyle=4" in style or "fontStyle=5" in style or "fontStyle=6" in style
                     or value.startswith("<u>") and value.endswith("</u>"))

            clean_value = value.replace("<u>", "").replace("</u>", "")

            SHAPE_MAP[id] = {
                "Type": "Attribute",
                "Value": clean_value,
                "PrimaryKey": is_pk
            }

        elif cell.get("edge", "") == "1":
            SHAPE_MAP[id] = {
                "Type": "EDGE",
                "Source": cell.get("source"),
                "Target": cell.get("target"),
                "Style": style,
                "Value": value
            }

    print("=== SHAPE_MAP (raw) ===")
    print_dict(SHAPE_MAP)


    for id, shape in list(SHAPE_MAP.items()):
        if shape["Type"] == "EDGE":
            source = shape["Source"]
            target = shape["Target"]
            style = shape["Style"]
            raw_value = shape.get("Value", "")
            cardinality = check_cardinality(style, raw_value) or 'None'

            if not source or not target:
                continue

            source_type = SHAPE_MAP.get(source, {}).get("Type")
            target_type = SHAPE_MAP.get(target, {}).get("Type")

            if target_type == "Attribute" and source_type in ("RELATION", "Entity"):
                SHAPE_MAP[source]["Attributes"].append(SHAPE_MAP[target])

            elif source_type == "Attribute" and target_type in ("RELATION", "Entity"):
                SHAPE_MAP[target]["Attributes"].append(SHAPE_MAP[source])


            elif source_type == "Entity" and target_type == "RELATION":
                if target in RELATIONSHIPS:
                    RELATIONSHIPS[target]["Connected Entities"].append((source, cardinality))
                else:
                    RELATIONSHIPS[target] = {
                        "Connected Entities": [(source, cardinality)]
                    }

            elif source_type == "RELATION" and target_type == "Entity":
                if source in RELATIONSHIPS:
                    RELATIONSHIPS[source]["Connected Entities"].append((target, cardinality))
                else:
                    RELATIONSHIPS[source] = {
                        "Connected Entities": [(target, cardinality)]
                    }

    print_dict(SHAPE_MAP)
    print("====RELATIONS====")
    print_dict(RELATIONSHIPS)

def get_keys(entity_id):
    entity = SHAPE_MAP.get(entity_id)
    if not entity or (entity["Type"] != "Entity" and entity["Type"] != "RELATION"):
        return [], []

    primary_keys = []
    all_keys = []
    for attribute in entity["Attributes"]:
        if attribute.get("PrimaryKey"):
            primary_keys.append(attribute["Value"])
        all_keys.append(attribute["Value"])

    return primary_keys, all_keys


def make_attribute_tuples(attributes, constraints=None):

    if constraints is None:
        constraints = []
    elif isinstance(constraints, str):
        constraints = [constraints]

    updated_attributes = []
    for attr in attributes:
        updated_attributes.append((attr, list(constraints)))
    return updated_attributes



def generate_sql():
    entities = {}

    for id, shape in SHAPE_MAP.items():
        if shape["Type"] == "Entity":
            entities[id] = {
                "Attributes": [],
                "ForeignKeys": [],
                "PrimaryKeys": [],
                "Comments": []   # keep comment storage
            }

    for relation, relation_data in RELATIONSHIPS.items():
        entities_connected = relation_data["Connected Entities"]
        if len(entities_connected) == 2:
            (entity1_id, cardinality1), (entity2_id, cardinality2) = entities_connected
            entity1_primary_keys, entity1_all_attr = get_keys(entity1_id)
            entity2_primary_keys, entity2_all_attr = get_keys(entity2_id)
            relation_primary_keys, relation_all_attr = get_keys(relation)
            if SHAPE_MAP[relation]["Weak"]:
                entity_1_is_weak = SHAPE_MAP[entity1_id]["Weak"]
                entity_2_is_weak = SHAPE_MAP[entity2_id]["Weak"]
                if (entity_1_is_weak == entity_2_is_weak):
                    print("Weak Relation but not Weak Entity and Strong Entity",{entity1_id, entity2_id})
                    # One-to-One weak
                if cardinality1 in ["Exactly 1", "Optional: 0 or 1"] and cardinality2 in ["Exactly 1", "Optional: 0 or 1"]:
                    if(entity_2_is_weak):
                        entities[entity2_id]["Attributes"].extend(
                            make_attribute_tuples(entity1_primary_keys)
                        )
                        entities[entity2_id]["ForeignKeys"].append(entity1_id)
                        entities[entity2_id]["PrimaryKeys"].extend(entity1_primary_keys)
                        entities[entity2_id]["Comments"].append("Weak 1–1: dependent PK = owner PK")
                    else:
                        entities[entity1_id]["Attributes"].extend(
                            make_attribute_tuples(entity2_primary_keys)
                        )
                        entities[entity1_id]["ForeignKeys"].append(entity2_id)
                        entities[entity1_id]["PrimaryKeys"].extend(entity2_primary_keys)
                        entities[entity1_id]["Comments"].append("Weak 1–1: dependent PK = owner PK")


                elif cardinality1 in ["Exactly 1", "Optional: 0 or 1"] and cardinality2 in ["0 or More", "1 or More"]:
                    if (entity_2_is_weak):
                        entities[entity2_id]["Attributes"].extend(
                            make_attribute_tuples(entity1_primary_keys)
                        )
                        entities[entity2_id]["ForeignKeys"].append(entity1_id)
                        entities[entity2_id]["PrimaryKeys"].extend(entity1_primary_keys)
                        entities[entity2_id]["Comments"].append("Weak 1–Many: PK = owner PK + partial key")
                    else:
                        entities[entity1_id]["Attributes"].extend(
                            make_attribute_tuples(entity2_primary_keys)
                        )
                        entities[entity1_id]["ForeignKeys"].append(entity2_id)
                        entities[entity1_id]["PrimaryKeys"].extend(entity2_primary_keys)
                        entities[entity2_id]["Comments"].append("Weak 1–Many: PK = owner PK + partial key")


                elif cardinality2 in ["Exactly 1", "Optional: 0 or 1"] and cardinality1 in ["0 or More", "1 or More"]:
                    (entity1_primary_keys, entity1_all_attr,
                     entity2_primary_keys, entity2_all_attr) = (
                        entity2_primary_keys, entity2_all_attr,
                        entity1_primary_keys, entity1_all_attr
                    )
                    if (entity_2_is_weak):
                        entities[entity2_id]["Attributes"].extend(
                            make_attribute_tuples(entity1_primary_keys)
                        )
                        entities[entity2_id]["ForeignKeys"].append(entity1_id)
                        entities[entity2_id]["PrimaryKeys"].extend(entity1_primary_keys)
                        entities[entity2_id]["Comments"].append("Why is the many-side weak????")
                    else:
                        entities[entity1_id]["Attributes"].extend(
                            make_attribute_tuples(entity2_primary_keys)
                        )
                        entities[entity1_id]["ForeignKeys"].append(entity2_id)
                        entities[entity1_id]["PrimaryKeys"].extend(entity2_primary_keys)
                        entities[entity2_id]["Comments"].append("Weak 1–Many: PK = owner PK + partial key")

                elif cardinality1 in ["0 or More", "1 or More"] and cardinality2 in ["0 or More", "1 or More"]:
                    entities[entity2_id]["Comments"].append("Detected Weak Many–Many: shouldn't exist")
                else:
                    pass
            else:
            # One to One
                if cardinality1 in ["Exactly 1", "Optional: 0 or 1"] and cardinality2 in ["Exactly 1", "Optional: 0 or 1"]:
                    if cardinality1.startswith("Optional"):
                        entities[entity1_id]["ForeignKeys"].append(entity2_id)
                        entities[entity1_id]["Attributes"].extend(
                            make_attribute_tuples(entity2_primary_keys, ["UNIQUE"])
                        )
                        entities[entity1_id]["Comments"].append("Optional 1–1: FK in Optional Side")
                    elif cardinality2.startswith("Optional"):
                        entities[entity2_id]["ForeignKeys"].append(entity1_id)
                        entities[entity2_id]["Attributes"].extend(
                            make_attribute_tuples(entity1_primary_keys, ["UNIQUE"])
                        )
                        entities[entity2_id]["Comments"].append("Optional 1–1: FK in Optional Side")
                    else:
                        entities[entity2_id]["ForeignKeys"].append(entity1_id)
                        entities[entity2_id]["Attributes"].extend(
                            make_attribute_tuples(entity1_primary_keys, ["UNIQUE", "NOT NULL"])
                        )
                        entities[entity2_id]["Comments"].append("Exact 1–1: enforced with UNIQUE + NOT NULL, FK can be either side")

                # One to Many
                elif (cardinality1 in ["Exactly 1", "Optional: 0 or 1"] and cardinality2 in ["0 or More", "1 or More"]):
                    #Entity 1 One
                    if(len(relation_primary_keys) > 0):
                        entities[relation] = {
                            "Attributes": make_attribute_tuples(relation_all_attr + entity2_primary_keys),
                            "ForeignKeys": [entity2_id],
                            "PrimaryKeys": relation_primary_keys + entity2_primary_keys,
                            "Comments": [
                                f"Table for one-to-many between {SHAPE_MAP[entity1_id]['Name']} and {SHAPE_MAP[entity2_id]['Name']} due to relations having primary key."]
                        }
                    else:
                        if(cardinality1 == "Exactly 1"):
                            entities[entity2_id]["Attributes"].extend(make_attribute_tuples(entity1_primary_keys,["NOT NULL"]))
                            entities[entity2_id]["ForeignKeys"].append(entity1_id)
                            entities[entity2_id]["Comments"].append(
                                f"Added FK to {SHAPE_MAP[entity1_id]['Name']} because {SHAPE_MAP[entity2_id]['Name']} is the many side."
                            )
                        else:
                            entities[entity2_id]["Attributes"].extend(
                                make_attribute_tuples(entity1_primary_keys))
                            entities[entity2_id]["ForeignKeys"].append(entity1_id)
                            entities[entity2_id]["Comments"].append(
                                f"Added FK to {SHAPE_MAP[entity1_id]['Name']} because {SHAPE_MAP[entity2_id]['Name']} is the many side."
                            )
                elif (cardinality2 in ["Exactly 1", "Optional: 0 or 1"] and cardinality1 in ["0 or More", "1 or More"]):
                    entity1_id, entity2_id = entity2_id, entity1_id
                    cardinality1, cardinality2 = cardinality2, cardinality1
                    if (len(relation_primary_keys) > 0):
                        entities[relation] = {
                            "Attributes": make_attribute_tuples(relation_all_attr + entity2_primary_keys),
                            "ForeignKeys": [entity2_id],
                            "PrimaryKeys": relation_primary_keys + entity2_primary_keys,
                            "Comments": [
                                f"Table for one-to-many between {SHAPE_MAP[entity1_id]['Name']} and {SHAPE_MAP[entity2_id]['Name']} due to relations having primary key."]
                        }
                    else:
                        if (cardinality2 == "0 or More"):
                            entities[entity2_id]["Attributes"].extend(
                                make_attribute_tuples(entity2_primary_keys))
                            entities[entity2_id]["ForeignKeys"].append(entity1_id)
                            entities[entity2_id]["Comments"].append(
                                f"Added FK to {SHAPE_MAP[entity1_id]['Name']} because {SHAPE_MAP[entity2_id]['Name']} is the many side."
                            )
                        else:
                            entities[entity2_id]["Attributes"].extend(
                                make_attribute_tuples(entity2_primary_keys))
                            entities[entity2_id]["ForeignKeys"].append(entity1_id)
                            entities[entity2_id]["Comments"].append(
                                f"Added FK to {SHAPE_MAP[entity1_id]['Name']} because {SHAPE_MAP[entity2_id]['Name']} is the many side."
                            )

                # Many to Many
                elif (cardinality1 in ["0 or More", "1 or More"]) and (cardinality2 in ["0 or More", "1 or More"]):
                    entities[relation] = {
                        "Attributes": relation_all_attr + entity1_primary_keys + entity2_primary_keys,
                        "ForeignKeys": [entity2_id, entity1_id],
                        "PrimaryKeys": relation_primary_keys + entity1_primary_keys + entity2_primary_keys,
                        "Comments": [f"Join table for many-to-many between {SHAPE_MAP[entity1_id]['Name']} and {SHAPE_MAP[entity2_id]['Name']}."]
                    }

    sql = []
    print_dict(entities)
    for entity_id, relation_data in entities.items():
        entity_primary_keys, entity_all_keys = get_keys(entity_id)
        entity_name = SHAPE_MAP[entity_id]["Name"]
        pk_cols = list(set(entity_primary_keys + relation_data["PrimaryKeys"]))
        cols = []
        constraints = []

        for attr_entry in relation_data["Attributes"]:
            if isinstance(attr_entry, tuple):
                attr_name, attr_constraints = attr_entry
                constraint_str = " ".join(attr_constraints) if attr_constraints else ""
                cols.append(f"{attr_name} VARCHAR(255) {constraint_str}".strip())
            else:
                cols.append(f"{attr_entry} VARCHAR(255)")

        for attr in entity_all_keys:
            cols.append(f"{attr} VARCHAR(255)")

        for fk_id in relation_data["ForeignKeys"]:
            fk_primary_keys, fk_all_keys = get_keys(fk_id)
            fk_name = SHAPE_MAP[fk_id]["Name"]
            for key in fk_primary_keys:
                constraints.append(f"FOREIGN KEY ({key}) REFERENCES {fk_name}({key})")

        if pk_cols:
            constraints.insert(0, f"PRIMARY KEY ({', '.join(pk_cols)})")

        all_defs = cols + constraints

        comments = "\n".join(f"-- {c}" for c in relation_data.get("Comments", []))
        if comments:
            sql.append(comments)

        sql.append(f"CREATE TABLE {entity_name} (\n    " + ",\n    ".join(all_defs) + "\n);")

    return "\n\n".join(sql)



if __name__ == '__main__':
    """input_file = "../ERDtoSQL Test/UMLTestsCardinality/uml_permutations/0_1(weak)_to_Many/0_1(weak)_to_Many.drawio"
    if os.path.exists(input_file):
        tree = ET.parse(input_file)
        root = tree.getroot()

        update_shape_map(root)
        print(generate_sql())
    else:
        print(f"File {input_file} not found")"""

    directory = "../ERDtoSQL Test/UMLTestsCardinality"

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".drawio"):
                file_path = os.path.join(root, file)
                SHAPE_MAP.clear()
                RELATIONSHIPS.clear()
                tree = ET.parse(file_path)
                xml_root = tree.getroot()

                update_shape_map(xml_root)

                base_name = os.path.splitext(file)[0]
                output_path = os.path.join(root, base_name + ".sql")

                with open(output_path, "w") as sql_file:
                    print(f"+++++++++++++++++++++++++++++++++++++writing to {output_path}+++++++++++++++++++++++++++++++++++++++++++++++++++")
                    sql_file.write(generate_sql())
