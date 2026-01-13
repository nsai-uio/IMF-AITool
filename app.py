import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
import re
import json
import threading
import uuid
from dotenv import load_dotenv
# from utils import get_pdf_vector, create_qa_chain 
# from utils import parse_json
import google.generativeai as genai
from PyPDF2 import PdfReader

# Load environment variables from .env file
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['VECTOR_STORE_FOLDER'] = 'vector_store'
app.config['PROCESSED_DATA_FOLDER'] = 'processed_data'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Ensure upload and vector store directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['VECTOR_STORE_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_DATA_FOLDER'], exist_ok=True)

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

def process_pdf_task(task_id, pdf_path, filename, processed_folder):
    try:
        task_status[task_id] = {'status': 'processing', 'progress': 5, 'message': 'Extracting text...'}
        
        # Extract text from the saved PDF
        pdf_text = ""
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            for page in reader.pages:
                pdf_text += page.extract_text() or ""

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
        json_path_comp = os.path.join(processed_folder, json_filename_comp)
        with open(json_path_comp, 'w') as f:
            json.dump(component_dict, f, indent=4)

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
        response = model.generate_content(full_prompt_func)
        res = response.text
        result_dict = parse_json(res)

        json_filename = os.path.splitext(filename)[0] + '.json'
        json_path = os.path.join(processed_folder, json_filename)
        with open(json_path, 'w') as f:
            json.dump(result_dict, f, indent=4)

        task_status[task_id] = {'status': 'completed', 'progress': 100, 'message': 'Processing complete!', 'processed_file': json_filename}
    except Exception as e:
        task_status[task_id] = {'status': 'error', 'message': str(e)}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    # List available processed JSON files to potentially display in the UI
    processed_files = []
    for f in os.listdir(app.config['PROCESSED_DATA_FOLDER']):
        if f.endswith('.json'):
            processed_files.append(f)
    return render_template('index.html', processed_files=processed_files)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(pdf_path)

        task_id = str(uuid.uuid4())
        thread = threading.Thread(target=process_pdf_task, args=(task_id, pdf_path, filename, app.config['PROCESSED_DATA_FOLDER']))
        thread.start()

        return jsonify({'task_id': task_id}), 202

    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/status/<task_id>')
def task_status_route(task_id):
    status = task_status.get(task_id, {'status': 'not_found'})
    return jsonify(status)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    question = data.get('question')
    filename = data.get('filename')
    
    if not question or not filename:
        return jsonify({'error': 'Missing question or filename'}), 400

    # The frontend sends the JSON filename, but we need the original PDF
    if filename.endswith('.json'):
        pdf_filename = os.path.splitext(filename)[0] + '.pdf'
    else:
        pdf_filename = filename

    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(pdf_filename))

    if not os.path.exists(pdf_path):
        return jsonify({'error': f'File "{pdf_filename}" not found. Please upload it first.'}), 404

    try:
        # Use PdfReader to extract text directly from the PDF file
        pdf_text = ""
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            pdf_text += page.extract_text() or ""

        # Create prompt for Gemini
        prompt = f"Based on the following document, please answer the question and provide the citation.\n\nDocument:\n\"\"\"\n{pdf_text}\n\"\"\"\n\nQuestion: {question}\n\nAnswer:"
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content(prompt)

        return jsonify({'answer': response.text})
    except Exception as e:
        return jsonify({'error': f'Error during question answering: {str(e)}'}), 500

# New endpoint to serve processed JSON data
@app.route('/get_processed_data/<filename>')
def get_processed_data(filename):
    json_path = os.path.join(app.config['PROCESSED_DATA_FOLDER'], secure_filename(filename))
    if os.path.exists(json_path):
        return send_from_directory(app.config['PROCESSED_DATA_FOLDER'], secure_filename(filename))
    else:
        return jsonify({'error': 'Processed data file not found.'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5001)
