import xml.etree.ElementTree as ET
import itertools
import os

# Input / output setup
input_file = "1.drawio"       # your template with "CARDINALITY 1" and "CARDINALITY 2"
base_output = "uml_permutations"
os.makedirs(base_output, exist_ok=True)

# UML multiplicities
multiplicities = ["1", "0..1", "*", "5..10"]

# Load template XML once
tree = ET.parse(input_file)
root = tree.getroot()

# Iterate over all permutations
for left, right in itertools.product(multiplicities, repeat=2):
    # Make a fresh copy of the XML
    new_tree = ET.ElementTree(ET.fromstring(ET.tostring(root)))
    new_root = new_tree.getroot()

    # Replace placeholders with UML multiplicities
    for cell in new_root.findall(".//mxCell"):
        if cell.get("edge") == "1":
            if cell.get("value") == "CARDINALITY 1":
                cell.set("value", left)
            elif cell.get("value") == "CARDINALITY 2":
                cell.set("value", right)

    # Create safe folder name
    safe_left = left.replace("*", "Many").replace("..", "_")
    safe_right = right.replace("*", "Many").replace("..", "_")
    folder_name = f"{safe_left}_to_{safe_right}"
    folder_path = os.path.join(base_output, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # File path inside that folder
    out_path = os.path.join(folder_path, f"{folder_name}.drawio")

    # Save
    new_tree.write(out_path, encoding="utf-8", xml_declaration=True)
    print(f"Created {out_path}")
