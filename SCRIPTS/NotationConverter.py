import xml.etree.ElementTree as ET
import re
import os

SHAPE_MAP = {

}

STYLE_MAP = {
    'chen(adapted)': {
        '1': {
            'end_style': 'endArrow=open;endFill=1;startArrow=none;startFill=0;',
            'start_style': 'endArrow=none;endFill=0;startArrow=open;startFill=1;',
        },
        'N': {
            'value': '1..*'
        },
        'M': {
            'value': '1..*'
        },
    },
    'crow': {
        '1': {
            'end_style': 'endArrow=ERmandOne;endFill=0;startArrow=none;startFill=0;',
            'start_style': 'endArrow=none;endFill=0;startArrow=ERmandOne;startFill=0;',
        },
        'N': {
            'end_style': 'endArrow=ERmany;endFill=0;startArrow=none;startFill=0;',
            'start_style': 'endArrow=none;endFill=0;startArrow=ERmany;startFill=0;',
        },
        'M': {
            'end_style': 'endArrow=ERmany;endFill=0;startArrow=none;startFill=0;',
            'start_style': 'endArrow=none;endFill=0;startArrow=ERmany;startFill=0;',
        }
    }
}


DEBUG = True

def debug_print(string):
    if DEBUG:
        print(string)

def debug_run(func, *args, **kwargs):
    if DEBUG:
        func(*args, **kwargs)

def update_SHAPE_MAP(tree):
    for cell in tree.iter("mxCell"):
        style = cell.get("style", "")
        id = cell.get("id", "")

        if style == "whiteSpace=wrap;html=1;align=center;" or style == "shape=ext;margin=3;double=1;whiteSpace=wrap;html=1;align=center;":
            SHAPE_MAP[id] = "ENTITY"
        elif "shape=rhombus" in style:
            SHAPE_MAP[id] = "RELATION"
        elif "1" == cell.get("edge",""):
            SHAPE_MAP[id] = "EDGE"

    print(f"SHAPE_MAP:{SHAPE_MAP}")
    return

def generate_drawio_with_arrows(input_file, chen_output_file, crow_output_file):
    # Parse original XML once
    tree = ET.parse(input_file)
    debug_print("File Contents:")
    debug_run(ET.dump, tree)

    root = tree.getroot()
    debug_print("\nExtract Root:")
    debug_run(ET.dump, root)

    update_SHAPE_MAP(root)

    # Deep copy for each output version
    chen_tree = ET.ElementTree(ET.fromstring(ET.tostring(root)))
    crow_tree = ET.ElementTree(ET.fromstring(ET.tostring(root)))

    # Update for Chen
    apply_arrow_styles(chen_tree, STYLE_MAP['chen(adapted)'])
    chen_tree.write(chen_output_file, encoding='utf-8', xml_declaration=True)
    print(f"Chen arrow version saved to: {chen_output_file}")

    # Update for Crow's Foot
    apply_arrow_styles(crow_tree, STYLE_MAP['crow'])
    crow_tree.write(crow_output_file, encoding='utf-8', xml_declaration=True)
    print(f"Crow’s Foot version saved to: {crow_output_file}")

def apply_arrow_styles(tree, style_map):
    root = tree.getroot()
    debug_print(f"Altering styles: based on {style_map}")
    for cell in root.iter('mxCell'):
        value = cell.attrib.get('value', '').strip()
        if value not in style_map:
            continue
        else:
            cell_str = ET.tostring(cell, encoding='unicode')
            debug_print(f"Found matching value '{value}' in cell:\n{cell_str}")

        original_style = cell.attrib.get('style', '')
        sourceid = cell.get("source", "")
        targetid = cell.get("target", "")

        if SHAPE_MAP[sourceid] == "ENTITY":
            if SHAPE_MAP[targetid] == "RELATION":
                #source is entity meaning start is needed
                debug_print(f"Entity located at {sourceid} -> Relation located at {targetid}")
                if("value" in style_map[value]):
                    cell.set('value', style_map[value]['value'])
                    debug_print(f"Setting Value to {style_map[value]['value']}")
                else:
                    cell.set('value', "")
                if("start_style" in style_map[value]):
                    style_parts = [p for p in original_style.split(';') if not p.startswith('endArrow=') and not p.startswith('endFill=') and not p.startswith( 'startArrow=') and not p.startswith('startFill=')]
                    style_parts.append(style_map[value]['start_style'])
                    updated_style = ';'.join(style_parts).strip(';')
                    debug_print(f"Setting Style to {updated_style}")
                    cell.set('style', updated_style)
            elif SHAPE_MAP[targetid] == "ENTITY":
                debug_print("ERROR Edge goes from Entity to Entity")
            else:
                debug_print("??????IDK")

        if SHAPE_MAP[targetid] == "ENTITY":
            if SHAPE_MAP[sourceid] == "RELATION":
                debug_print(
                    f"Relation located at {sourceid} -> Entity located at {targetid}")
                #target is entity meaning end_style is needed
                if("value" in style_map[value]):
                    debug_print(f"Setting Value to {STYLE_MAP[value]['value']}")
                    cell.set('value', STYLE_MAP[value]['value'])
                else:
                    cell.set('value', "")
                if("end_style" in style_map[value]):
                    style_parts = [p for p in original_style.split(';') if not p.startswith('endArrow=') and not p.startswith('endFill=') and not p.startswith( 'startArrow=') and not p.startswith('startFill=')]
                    style_parts.append(style_map[value]['end_style'])
                    updated_style = ';'.join(style_parts).strip(';')
                    debug_print(f"Setting Style to {updated_style}")
                    cell.set('style', updated_style)
            elif SHAPE_MAP[targetid] == "RELATION":
                debug_print("ERROR Edge goes from Relation to Relation")
            else:
                debug_print("??????IDK")


if __name__ == '__main__':
    directory_name = "../TestFiles"
    for root, dirs, files in os.walk(directory_name):
        for file in files:
            if file.endswith("_chen_arrows.drawio") or file.endswith("_crows_foot.drawio"):
                os.remove(os.path.join(root, file))
                print(f"Deleted old output: {file}")
    for root, dirs, files in os.walk(directory_name):
        for file in files:
            if file.endswith(".drawio"):
                input_path = os.path.join(root, file)
                base_name = os.path.splitext(file)[0]
                chen_output = os.path.join(root, f"{base_name}_chen_arrows.drawio")
                crow_output = os.path.join(root, f"{base_name}_crows_foot.drawio")
                generate_drawio_with_arrows(
                    input_file=input_path,
                    chen_output_file=chen_output,
                    crow_output_file=crow_output
                )