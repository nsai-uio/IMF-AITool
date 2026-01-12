import json
import os
import time
import random

def convert_json_to_imf(input_path, output_path):
    """
    Converts a JSON system description to an IMF file format.
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
    
    # Map TagID to Node index for updating children later
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

    # Iterate source data for Transfer Edges (connectedTo)
    # for system_name, details in source_data.items():
    #     tag_id = details.get("tagID")
    #     connected_to_list = details.get("connectedTo", [])
    #     for target_name in connected_to_list:
    #         target_id = system_name_to_id.get(target_name)
    #         if target_id:
    #             edges.append(create_edge(tag_id, target_id, "transfer"))
    #             edge_counter += 1

    imf_content = {
        "nodes": nodes,
        "edges": edges
    }

    with open(output_path, 'w') as f:
        json.dump(imf_content, f, indent=2)
    
    print(f"Generated IMF file at: {output_path}")

if __name__ == "__main__":
    input_json = "/Users/yanzho/Codes/SIM/processed_data/PATENT_gas_cooling_system.json"
    output_imf = "/Users/yanzho/Codes/SIM/converted_gas_cooling_system.imf"
    convert_json_to_imf(input_json, output_imf)