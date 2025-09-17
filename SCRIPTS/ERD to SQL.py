import xml.etree.ElementTree as ET
import os

SHAPE_MAP = {}
RELATIONSHIPS = {}

DEBUG = True

#Chen or Crow's Foot or UML
CURRENT_NOTATION = "Crow's Foot"

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
            "value": "5..10"
        }
    }
}


def check_cardinality(style, value):
    # ex. "1": {
    #             "value": "1"
    #         },
    for cardinality, cardinality_mapping in style_hashmap[CURRENT_NOTATION].items():
        if "value" in cardinality_mapping:
            if value == cardinality_mapping["value"]:
                return cardinality
        elif "end_style" in cardinality_mapping:
            if (cardinality_mapping["end_style"]) in style or (cardinality_mapping["start_style"]) in style:
                return cardinality

    if (CURRENT_NOTATION == "Chen" and (not style or style == "") and (not value or value == "")):
        return "0 or More"
    if CURRENT_NOTATION == "Chen" and "endArrow=none;endFill=0;startArrow=none;startFill=0;" in style:
        return "0 or More"
    if CURRENT_NOTATION == "Chen" and ("endArrow=blockThin;" in style or "startArrow=blockThin;" in style):
        return "Optional: 0 or 1"
    if CURRENT_NOTATION == "Chen(simple)" and (value == "M"):
        return "0 or More"
    return None


def debug_print(string):
    if DEBUG:
        print(string)

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


def update_shape_map(tree):
    for cell in tree.iter("mxCell"):
        style = cell.get("style", "")
        id = cell.get("id", "")
        value = cell.get("value", "").strip()

        if style.startswith("shape=rectangle;whiteSpace=wrap;html=1;") or style.startswith("whiteSpace=wrap;html=1;"):
            SHAPE_MAP[id] = {
                "Type": "Entity",
                "Weak": False,
                "Name": value,
                "Attributes": []
            }

        elif style.startswith("shape=ext;margin=3;double=1;whiteSpace=wrap;html=1;align=center;"):
            SHAPE_MAP[id] = {
                "Type": "Entity",
                "Weak": True,
                "Name": value,
                "Attributes": []
            }

        elif "rhombus" in style:
            SHAPE_MAP[id] = {
                "Type": "RELATION",
                "Name": value,
                "Attributes": []
            }

        elif "ellipse" in style:
            is_pk = "fontStyle=4" in style or "fontStyle=5" in style or "fontStyle=6" in style
            SHAPE_MAP[id] = {
                "Type": "Attribute",
                "Value": value,
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
    debug_print("=== SHAPE_MAP (raw) ===")
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

            # One to One
            if cardinality1 in ["Exactly 1", "Optional: 0 or 1"] and cardinality2 in ["Exactly 1", "Optional: 0 or 1"]:
                if cardinality1.startswith("Optional"):
                    entities[entity1_id]["ForeignKeys"].append(entity2_id)
                    entities[entity1_id]["Attributes"].extend(relation_all_attr + entity2_primary_keys)
                    entities[entity1_id]["PrimaryKeys"].extend(relation_primary_keys + entity2_primary_keys)
                    entities[entity1_id]["Comments"].append(
                        f"Added FK to {SHAPE_MAP[entity2_id]['Name']} (optional participation in one-to-one)."
                    )
                elif(cardinality2.startswith("Optional")):
                    entities[entity2_id]["ForeignKeys"].append(entity1_id)
                    entities[entity2_id]["Attributes"].extend(relation_all_attr + entity1_primary_keys)
                    entities[entity2_id]["PrimaryKeys"].extend(relation_primary_keys + entity1_primary_keys)
                    entities[entity2_id]["Comments"].append(
                        f"Added FK to {SHAPE_MAP[entity1_id]['Name']} (optional participation in one-to-one)."
                    )
                else:
                    entities[entity2_id]["ForeignKeys"].append(entity1_id)
                    entities[entity2_id]["Attributes"].extend(relation_all_attr + entity1_primary_keys)
                    entities[entity2_id]["PrimaryKeys"].extend(relation_primary_keys + entity1_primary_keys)
                    entities[entity2_id]["Comments"].append(
                        f"Added FK to {SHAPE_MAP[entity1_id]['Name']} (neither has optional participation in one-to-one)."
                    )

            # One to Many
            elif (cardinality1 == "Exactly 1" and cardinality2 in ["0 or More", "1 or More"]):
                entities[entity2_id]["ForeignKeys"].append(entity1_id)
                entities[entity2_id]["Comments"].append(
                    f"Added FK to {SHAPE_MAP[entity1_id]['Name']} because {SHAPE_MAP[entity2_id]['Name']} is the many side."
                )
            elif (cardinality2 == "Exactly 1" and cardinality1 in ["0 or More", "1 or More"]):
                entities[entity1_id]["ForeignKeys"].append(entity2_id)
                entities[entity1_id]["Comments"].append(
                    f"Added FK to {SHAPE_MAP[entity2_id]['Name']} because {SHAPE_MAP[entity1_id]['Name']} is the many side."
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
    for entity_id, relation_data in entities.items():
        entity_primary_keys, entity_all_keys = get_keys(entity_id)
        entity_name = SHAPE_MAP[entity_id]["Name"]
        pk_cols = list(set(entity_primary_keys + relation_data["PrimaryKeys"]))
        cols = []
        constraints = []

        for attr in relation_data["Attributes"] + entity_all_keys:
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
    input_file = "../ERDtoSQL Test/Crow_Foot_Test.drawio"
    if os.path.exists(input_file):
        tree = ET.parse(input_file)
        root = tree.getroot()

        update_shape_map(root)
        print(generate_sql())
    else:
        print(f"File {input_file} not found")
