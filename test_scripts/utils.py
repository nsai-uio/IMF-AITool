import os
import time
import random
import json
import re
import threading
import uuid
from datetime import datetime
import google.generativeai as genai
from PyPDF2 import PdfReader

# Try to import secure_filename, provide fallback if werkzeug is not installed
try:
    from werkzeug.utils import secure_filename
except ImportError:
    def secure_filename(filename):
        return re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)

# Configuration for standalone script execution
# Folders are created relative to this script's location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(BASE_DIR, 'results')
os.makedirs(RESULT_DIR, exist_ok=True)

CONFIG = {
    'UPLOAD_FOLDER': os.path.join(BASE_DIR, 'uploads'),
    'COMPONENTS_FOLDER': os.path.join(RESULT_DIR, 'components'),
    'RELATIONS_FOLDER': os.path.join(RESULT_DIR, 'relations'),
    'LOGS_FOLDER': os.path.join(RESULT_DIR, 'logs'),
    'SELF_CHECKED_DATA_FOLDER': os.path.join(RESULT_DIR, 'self_checked_data'),
    'IMF_DATA_FOLDER': os.path.join(RESULT_DIR, 'imf_data'),
    'ALLOWED_EXTENSIONS': {'pdf'}
}

# Ensure directories exist
for folder in CONFIG.values():
    if isinstance(folder, str):
        os.makedirs(folder, exist_ok=True)

# Global dictionary to store task status
task_status = {}

def parse_json(results_string):
    cleaned_string = results_string.replace('\n', '')
    # matches a closing quote followed by a closing brace or bracket, followed by an opening quote (indicating missing comma)
    json_string = re.sub(r'"\s*([\]}])\s*"', r'"\1,""', cleaned_string)
    # Add commas after objects and arrays if not followed by a comma or end of object/array
    json_string = re.sub(r'([\]}])\s*([^\],})\s*\n])', r'\1,\2', json_string)
    # Remove trailing commas before closing braces
    json_string = re.sub(r',\s*}', '}', json_string)
    match = re.search(r'\{.*\}', json_string, re.DOTALL)
    if match:
        content = match.group(0)
        # print(content)
    else:
        print("No content found between curly braces.")
    
    try:
        res_dict = json.loads(content)
        return res_dict
    except json.JSONDecodeError as e:
        if "Expecting ',' delimiter" in str(e):
            print(f"JSON error detected: {e}")
            # Attempt to fix the JSON by adding a closing bracket
            fixed_json_string = content.rstrip() + '}'
            try:
                # Try to load the fixed JSON string
                res_dict = json.loads(fixed_json_string)
                print("JSON was fixed and is now valid")
                return res_dict
            except json.JSONDecodeError as e:
                print(f"JSON format error after attempting to fix: {e}")
                return None
        else:
            print(f"JSON format error: {e}")
        return {}

def step1_components(task_id, pdf_path, filename, components_folder, api_key):
    """
    Identical logic to extract_components_task in app_user_panel.py
    """
    try:
        genai.configure(api_key=api_key)
        task_status[task_id] = {'status': 'processing', 'progress': 5, 'message': 'Extracting text...'}
        
        # Extract text from the saved PDF
        pdf_text = ""
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            for page in reader.pages:
                pdf_text += page.extract_text() or ""

        # Save text to file for step 2 (optimization)
        txt_path = os.path.splitext(pdf_path)[0] + '.txt'
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(pdf_text)

        task_status[task_id] = {'status': 'processing', 'progress': 25, 'message': 'Identifying components...'}

        # Patonomy prompt
        extraction_prompt = """please read the pdf and answer three questions only based on the pdf: 1) determine the name of the system as "system_name"; 2) find all components of this system as values of the key "system_name", and these components as keys of next level dictionary; 2) find all subcomponents of the components as values of dictionary, and as key of next dictionary. If no subcomponents are found, put an empty value{{}}; 3) To each subcomponent, please find their subcomponents and put them in a list, as value of subcomponent. If no sub-subcomponents are found, put an empty list as value. DO NOT forget the tagID of each component to distinguish different components with the same name but in differnent (sub)systems, usually a number or the combinition of number and letters following the system name.

            If the Cooling system has the following components: Pump System, Tank System, Gas chiller, Coolant cooler, and each components has some subcomponents, and subcomponents has sub-subcomponents, the sub-subcomponents are put in the list and separated by comma. 
            Example format of your response should be like following json format, no extra sentences are needed:

            ```json
            {{"Cooling system_A001":
                {{"pump system_B22": 
                    {{"pump_B223": ["subcomponent_1","subcomponent_2"],
                    "motor_B224":["subcomponent_1"],
                    "safety instrument_B225": ["subcomponent_1"]}},
                "tank system_C99": {{}},
                "gas chiller_K12": {{}}
                }}
            }}
            ```"""
        # 3. save Partonomy result
        full_prompt_part = f"Document:\n\"\"\"\n{pdf_text}\n\"\"\"\n\nInstructions:\n{extraction_prompt}"
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content(full_prompt_part)
        component_dict = parse_json(response.text)

        json_filename_comp = os.path.splitext(filename)[0] + '_components.json'
        json_path_comp = os.path.join(components_folder, json_filename_comp)
        with open(json_path_comp, 'w') as f:
            json.dump(component_dict, f, indent=4)

        task_status[task_id] = {'status': 'completed', 'progress': 100, 'message': 'Component extraction complete!', 'processed_file': json_filename_comp}
    except Exception as e:
        task_status[task_id] = {'status': 'error', 'message': str(e)}
        print(f"Error in step1_components: {e}")

def step2_relations(task_id, filename, components_folder, relations_folder, upload_folder, api_key):
    """
    Identical logic to extract_relations_task in app_user_panel.py
    """
    try:
        genai.configure(api_key=api_key)
        task_status[task_id] = {'status': 'processing', 'progress': 5, 'message': 'Loading data...'}
        
        # Load text from txt file (saved in step 1)
        txt_filename = os.path.splitext(filename)[0] + '.txt'
        txt_path = os.path.join(upload_folder, txt_filename)
        
        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8') as f:
                pdf_text = f.read()
        else:
            # Fallback to PDF if txt missing
            pdf_filename = os.path.splitext(filename)[0] + '.pdf'
            pdf_path = os.path.join(upload_folder, pdf_filename)
            if not os.path.exists(pdf_path):
                raise FileNotFoundError("Source PDF/Text not found.")
            pdf_text = ""
            with open(pdf_path, 'rb') as f:
                reader = PdfReader(f)
                for page in reader.pages:
                    pdf_text += page.extract_text() or ""

        # Load components
        json_filename_comp = os.path.splitext(filename)[0] + '_components.json'
        json_path_comp = os.path.join(components_folder, json_filename_comp)
        
        if not os.path.exists(json_path_comp):
            raise FileNotFoundError("Components file not found. Run Step 1 first.")
            
        with open(json_path_comp, 'r') as f:
            component_dict = json.load(f)

        task_status[task_id] = {'status': 'processing', 'progress': 60, 'message': 'Constructing information model...'}

        # prompt for all relations
        func_prompt = """Please construct the information model for this system based on the pdf and the hierarchy of system components extracted in the {component_dict}. The information model should cover all system components in the {component_dict}, and contain relations for each system component: tagID, partOf, connectedTo, fulfills, hasTerminal. The explanation of each relation is shown as follows:
            "tagID": the ID of a system component defined in the pdf, usually a number or the combinition of number and letters.
            "partOf": relates two system components to specify that one component (values of a key or elements in the list in {component_dict}) is a direct part of another component (keys of {component_dict}). All components are part of the system name (first key of the dictionary). 
            "connectedTo": relates two system components to specify that one component is physically connected to another. 
            "fulfills": relates one or more functionalities to one component. The functionality should be a single phase as short as possible, or a list of several short phases. If no functionality is found, return an empty list.
            "hasTerminal": relates a component to one or more Terminal. A Terminal is an [Element] that represents a point of interaction or communication for exactly one component, and hence specifies an input and/or output that the component produces and/or receives.

            Here is an format example of the result:

            {{
            "Cooling system":{{
                "tagID": "JG1"
                "partOf": [], # no partOf for the whole system
                "fulfills": [cooling,...]
                "connectedTo": [] # no connected components for the whole system
                "hasTerminal": [Cooled Gas, Warm Seawater, ...]
                }},
            "REP assembly 810":{{
                "tagID": "A-GD03"
                "partOf": [Cooling system], 
                "fulfills": [function1, function2,],
                "connectedTo": [Voltage Transforming System, ...],
                "hasTerminal": [Warm Seawater, ...],
                }}
            }}

            """
        full_prompt_func = f"Document:\n\"\"\"\n{pdf_text}\n\"\"\"\n\component_dict:\n{component_dict}\n\nInstructions:\n{func_prompt}"
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content(full_prompt_func)
        res = response.text
        result_dict = parse_json(res)

        json_filename = os.path.splitext(filename)[0] + '.json'
        json_path = os.path.join(relations_folder, json_filename)
        with open(json_path, 'w') as f:
            json.dump(result_dict, f, indent=4)

        task_status[task_id] = {'status': 'completed', 'progress': 100, 'message': 'Relation extraction complete!', 'processed_file': json_filename}
    except Exception as e:
        task_status[task_id] = {'status': 'error', 'message': str(e)}
        print(f"Error in step2_relations: {e}")

def self_verification(task_id, json_filename, api_key):
    """
    Identical logic to self_check_task in app_user_panel.py
    """
    try:
        genai.configure(api_key=api_key)
        task_status[task_id] = {'status': 'processing', 'progress': 5, 'message': 'Starting self-check...'}

        # 1. Define paths and load data
        processed_json_path = os.path.join(CONFIG['RELATIONS_FOLDER'], json_filename)
        pdf_filename = os.path.splitext(json_filename)[0] + '.pdf'
        pdf_path = os.path.join(CONFIG['UPLOAD_FOLDER'], secure_filename(pdf_filename))

        if not os.path.exists(processed_json_path) or not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Required file not found. Checked for {json_filename} and {pdf_filename}.")

        with open(processed_json_path, 'r') as f:
            data = json.load(f)

        pdf_text = ""
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            for page in reader.pages:
                pdf_text += page.extract_text() or ""

        task_status[task_id] = {'status': 'processing', 'progress': 20, 'message': 'Generating verification claims...'}

        # 2. Generate questions (claims) from the JSON data
        claims_to_verify = []
        for component, details in data.items():
            # "partOf" claims
            if "partOf" in details and details["partOf"]:
                for parent in details["partOf"]:
                    if parent:
                        claims_to_verify.append({
                            "type": "partOf", "component": component, "value": parent,
                            "claim": f"Is {component} part of {parent}?"
                        })
            # "fulfills" claims
            if "fulfills" in details and details["fulfills"]:
                for function in details["fulfills"]:
                    if function:
                        claims_to_verify.append({
                            "type": "fulfills", "component": component, "value": function,
                            "claim": f"Can {component} fulfill the function: '{function}'?"
                        })

        if not claims_to_verify:
            task_status[task_id] = {'status': 'completed', 'progress': 100, 'message': 'No claims to verify in the file.'}
            return

        claims_text = "\n".join([f"{i+1}. {c['claim']}" for i, c in enumerate(claims_to_verify)])
        task_status[task_id] = {'status': 'processing', 'progress': 40, 'message': 'Querying language model...'}

        # 3. Construct prompt and query Gemini
        verification_prompt = f"""You are a system engineering expert. Based on the provided document, please verify the following claims. For each claim, answer with "Yes" or "No". If the answer is "No", please provide a brief explanation based on the document.

Document:
\"\"\"
{pdf_text}
\"\"\"

Claims to verify:
{claims_text}

Please provide your answers in a JSON format as a list of objects, where each object has "claim_number" (integer), "answer" ("Yes" or "No"), and "explanation" (string, empty if answer is "Yes", provide evidence if answer is "No").
Example for your response:
```json
[
  {{
    "claim_number": 1,
    "answer": "Yes",
    "explanation": ""
  }},
  {{
    "claim_number": 2,
    "answer": "No",
    "explanation": "The document states it does W, not Z."
  }}
]
```"""
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content(verification_prompt)

        task_status[task_id] = {'status': 'processing', 'progress': 80, 'message': 'Processing results...'}

        # 4. Process results, log, and update JSON
        match = re.search(r'```json\s*([\s\S]*?)\s*```', response.text)
        json_text = match.group(1) if match else response.text
        verification_results = json.loads(json_text)

        modified_data = json.loads(json.dumps(data))  # Deep copy
        corrections_log = []

        for result in verification_results:
            claim_num = result.get('claim_number')
            answer = result.get('answer')

            if answer == "No" and claim_num is not None and 1 <= claim_num <= len(claims_to_verify):
                original_claim_info = claims_to_verify[claim_num - 1]
                log_entry = f"Question: {original_claim_info['claim']}\nAnswer: No\nExplanation: {result.get('explanation', 'N/A')}\n---\n"
                corrections_log.append(log_entry)

                comp, val_to_remove = original_claim_info['component'], original_claim_info['value']
                if original_claim_info['type'] == 'partOf' and val_to_remove in modified_data[comp].get('partOf', []):
                    modified_data[comp]['partOf'].remove(val_to_remove)
                elif original_claim_info['type'] == 'fulfills' and val_to_remove in modified_data[comp].get('fulfills', []):
                    modified_data[comp]['fulfills'].remove(val_to_remove)

        # Always save the checked file, even if no corrections were made
        checked_filename = os.path.splitext(json_filename)[0] + '_checked.json'
        checked_filepath = os.path.join(CONFIG['SELF_CHECKED_DATA_FOLDER'], checked_filename)
        with open(checked_filepath, 'w') as f:
            json.dump(modified_data, f, indent=4)

        if corrections_log:
            log_filename = os.path.splitext(json_filename)[0] + "_self_check.log"
            log_filepath = os.path.join(CONFIG['LOGS_FOLDER'], log_filename)
            with open(log_filepath, 'a') as log_file:
                log_file.write(f"\n--- Self-check for {json_filename} at {datetime.now()} ---\n")
                log_file.writelines(corrections_log)

            message = f'Self-check complete. {len(corrections_log)} corrections made. See {log_filename} and {checked_filename}.'
        else:
            message = 'Self-check complete. No errors found.'

        task_status[task_id] = {'status': 'completed', 'progress': 100, 'message': message}
    except Exception as e:
        task_status[task_id] = {'status': 'error', 'message': str(e)}
        print(f"Error in self_verification: {e}")

def convert_to_imf(input_path, output_path):
    """
    Identical logic to convert_json_to_imf in app_user_panel.py
    """
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at {input_path}")
        return

    with open(input_path, 'r') as f:
        source_data = json.load(f)

    nodes = []
    edges = []
    
    # Map System Name to TagID for resolving references
    system_name_to_id = {name: details.get("tagID") for name, details in source_data.items()}
    
    id_to_node_index = {}
    id_to_label = {}
    id_to_node_map = {}

    # --- Hierarchical Layout Logic ---
    nodes_tree = {}
    roots = []

    # 1. Initialize tree structure
    for system_name in source_data:
        nodes_tree[system_name] = {
            "children": [],
            "subtree_width": 0,
            "position": {"x": 0, "y": 0}
        }

    # 2. Build parent-child relationships
    for system_name, details in source_data.items():
        part_of_list = details.get("partOf", [])
        if part_of_list:
            parent_name = part_of_list[0]  # Assuming one primary parent
            if parent_name in nodes_tree:
                nodes_tree[parent_name]["children"].append(system_name)
        else:
            roots.append(system_name)

    # 3. Define layout functions
    X_GAP = 250
    Y_GAP = 150

    def calculate_subtree_width(node_name):
        node = nodes_tree[node_name]
        if not node["children"]:
            node["subtree_width"] = X_GAP
            return X_GAP
        
        total_width = sum(calculate_subtree_width(child_name) for child_name in node["children"])
        width = max(X_GAP, total_width)
        node["subtree_width"] = width
        return width

    def layout_tree(node_name, x_start, y_start):
        node = nodes_tree[node_name]
        children_total_width = sum(nodes_tree[child_name]["subtree_width"] for child_name in node["children"]) if node["children"] else 0
        parent_x = x_start + (max(0, children_total_width - X_GAP) / 2)
        node["position"] = {"x": parent_x, "y": y_start}
        current_x_child = x_start
        for child_name in node["children"]:
            layout_tree(child_name, current_x_child, y_start + Y_GAP)
            current_x_child += nodes_tree[child_name]["subtree_width"]

    # 4. Apply layout algorithm
    current_x_root = 0
    for root_name in roots:
        calculate_subtree_width(root_name)
        layout_tree(root_name, current_x_root, 0)
        current_x_root += nodes_tree[root_name]["subtree_width"] + X_GAP
    # --- End of Layout Logic ---

    current_label_index = 1
    function_data_list = []

    # 1. Create Nodes
    for system_name, details in source_data.items():
        tag_id = details.get("tagID")
        
        # Determine Parent
        part_of_list = details.get("partOf", [])
        parent_id = "void"
        direct_part_of = ""
        
        if part_of_list:
            # Take the first parent as the primary parent
            parent_name = part_of_list[0]
            if parent_name in system_name_to_id:
                parent_id = system_name_to_id[parent_name]
                direct_part_of = parent_id

        # Get pre-calculated position
        position = nodes_tree[system_name]["position"]

        # Generate random createdAt timestamp (milliseconds)
        created_at = int(time.time() * 1000) - random.randint(0, 10000000)

        # --- Create Function Nodes ---
        fulfills_list = details.get("fulfills", [])
        func_ids = []

        for i, func_desc in enumerate(fulfills_list):
            func_tag_id = f"{tag_id}_func_{i}"
            func_label = f"Block{current_label_index}"
            current_label_index += 1
            id_to_label[func_tag_id] = func_label

            function_data_list.append({
                "id": func_tag_id,
                "label": func_label,
                "desc": func_desc,
                "product_id": tag_id,
                "product_x": position["x"],
                "product_y": position["y"],
                "index": i
            })
            func_ids.append(func_tag_id)

        # --- Create Product Node ---
        label = f"Block{current_label_index}"
        current_label_index += 1
        id_to_label[tag_id] = label

        node = {
            "data": {
                "parent": parent_id,
                "children": [], # Populated in pass 2
                "terminals": [],
                "fulfilledBy": [{"id": fid} for fid in func_ids], # Product fulfilledBy Function
                "fulfills": [],
                "directParts": [], # Populated in pass 2
                "connectedTo": [],
                "connectedBy": [],
                "directPartOf": direct_part_of,
                "customName": system_name,
                "customAttributes": [],
                "aspect": "product",
                "label": system_name,
                "label": label,
                "createdAt": created_at,
                "updatedAt": created_at,
                "createdBy": "system",
                "width": 110,
                "height": 66
            },
            "width": 110,
            "height": 66,
            "id": tag_id,
            "position": position,
            "type": "block",
            "selected": False
        }
        
        nodes.append(node)
        id_to_node_map[tag_id] = node

    # 2. Layout and Create Function Nodes
    # Sort by product X, then product Y, then index
    function_data_list.sort(key=lambda k: (k['product_x'], k['product_y'], k['index']))

    current_func_x = 0
    FUNC_Y = -400
    FUNC_X_GAP = 150 

    for func_data in function_data_list:
        # Determine X: Try to align with product, but ensure no overlap with previous
        target_x = func_data['product_x']
        if current_func_x < target_x:
            current_func_x = target_x
        
        position = {"x": current_func_x, "y": FUNC_Y}
        current_func_x += FUNC_X_GAP

        func_created_at = int(time.time() * 1000) - random.randint(0, 10000000)
        func_node = {
            "data": {
                "parent": "void",
                "children": [],
                "terminals": [],
                "fulfilledBy": [], 
                "fulfills": [{"id": func_data['product_id']}], # Function fulfills Product
                "directParts": [],
                "connectedTo": [],
                "connectedBy": [],
                "directPartOf": "",
                "customName": func_data['desc'],
                "customAttributes": [],
                "aspect": "function",
                "label": func_data['label'],
                "createdAt": func_created_at,
                "updatedAt": func_created_at,
                "createdBy": "system",
                "width": 110,
                "height": 66
            },
            "width": 110,
            "height": 66,
            "id": func_data['id'],
            "position": position,
            "type": "block",
            "selected": False
        }
        nodes.append(func_node)
        id_to_node_map[func_data['id']] = func_node

    # 3. Populate Children (Data)
    for node in nodes:
        if node["data"]["aspect"] == "product":
            parent_id = node["data"]["parent"]
            if parent_id != "void" and parent_id in id_to_node_map:
                parent_node = id_to_node_map[parent_id]
                child_ref = {"id": node["id"]}
                parent_node["data"]["children"].append(child_ref)
                parent_node["data"]["directParts"].append(child_ref)

    # 4. Create Edges
    edge_counter = 0
    
    def create_edge(source, target, edge_type):
        nonlocal edge_counter
        source_label = id_to_label.get(source, "Unknown")
        target_label = id_to_label.get(target, "Unknown")
        
        # Determine spatial relation
        source_dir, target_dir = "right", "left"
        if source in id_to_node_map and target in id_to_node_map:
            s_pos = id_to_node_map[source]["position"]
            t_pos = id_to_node_map[target]["position"]
            dx = t_pos["x"] - s_pos["x"]
            dy = t_pos["y"] - s_pos["y"]
            if abs(dx) >= abs(dy):
                if dx >= 0: source_dir, target_dir = "right", "left"
                else: source_dir, target_dir = "left", "right"
            else:
                if dy >= 0: source_dir, target_dir = "bottom", "top"
                else: source_dir, target_dir = "top", "bottom"

        edge_created_at = int(time.time() * 1000) - random.randint(0, 10000000)
        edge_id = f"reactflow__edge-{source}-{target}-{edge_type}"
        
        return {
            "id": edge_id,
            "source": source,
            "sourceHandle": f"{source_label}_{source_dir}_source",
            "target": target,
            "targetHandle": f"{target_label}_{target_dir}_target",
            "type": edge_type,
            "data": {
                "id": str(edge_counter),
                "createdAt": edge_created_at,
                "updatedAt": edge_created_at,
                "lockConnection": False,
                "label": f"Edge {edge_counter}",
                "createdBy": "system"
            },
            "selected": False
        }

    # Iterate nodes for Part and Fulfilled edges
    for node in nodes:
        source_id = node["id"]
        
        # Part Edges: Child -> Parent
        if node["data"]["aspect"] == "product":
            parent_id = node["data"]["parent"]
            if parent_id != "void":
                edges.append(create_edge(source_id, parent_id, "part"))
                edge_counter += 1

        # Fulfilled Edges: Product -> Function
        # (Based on data.fulfilledBy which we populated earlier)
        if node["data"]["aspect"] == "product":
            for func_ref in node["data"]["fulfilledBy"]:
                func_id = func_ref["id"]
                edges.append(create_edge(source_id, func_id, "fulfilled"))
                edge_counter += 1

    imf_content = {
        "nodes": nodes,
        "edges": edges
    }

    with open(output_path, 'w') as f:
        json.dump(imf_content, f, indent=2)
    
    print(f"Generated IMF file at: {output_path}")