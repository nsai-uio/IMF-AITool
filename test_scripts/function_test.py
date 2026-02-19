import os
import uuid
import time
import sys
from utils import step1_components, step2_relations, self_verification, convert_to_imf, CONFIG, task_status

def main():
    print("=== Function Testing Script ===")
    
    # 1. API Key Setup
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        api_key = input("Please enter your Google API Key: ").strip()
    
    if not api_key:
        print("Error: API Key is required.")
        return

    # 2. File Selection
    upload_folder = CONFIG['UPLOAD_FOLDER']
    print(f"\nLooking for PDFs in: {upload_folder}")
    
    # List PDFs
    pdfs = [f for f in os.listdir(upload_folder) if f.lower().endswith('.pdf')]
    
    if not pdfs:
        print("No PDF files found in the uploads folder.")
        print("Please place a PDF file in 'scripts/uploads' and try again.")
        return
    
    print("Available PDFs:")
    for i, f in enumerate(pdfs):
        print(f"{i+1}. {f}")
    
    try:
        choice = int(input("\nSelect a file number to process: "))
        if 1 <= choice <= len(pdfs):
            filename = pdfs[choice-1]
        else:
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return

    pdf_path = os.path.join(upload_folder, filename)
    print(f"\nProcessing: {filename}")

    # 3. Step 1: Components
    print("\n--- Step 1: Extracting Components ---")
    task_id_1 = str(uuid.uuid4())
    step1_components(task_id_1, pdf_path, filename, CONFIG['COMPONENTS_FOLDER'], api_key)
    
    status_1 = task_status.get(task_id_1)
    if status_1 and status_1['status'] == 'completed':
        print("Step 1 Completed Successfully.")
        print(f"Output: {status_1.get('processed_file')}")
    else:
        print(f"Step 1 Failed: {status_1.get('message') if status_1 else 'Unknown error'}")
        return

    # 4. Step 2: Relations
    print("\n--- Step 2: Extracting Relations ---")
    task_id_2 = str(uuid.uuid4())
    # Note: step2_relations expects the filename (base name or pdf name)
    step2_relations(task_id_2, filename, CONFIG['COMPONENTS_FOLDER'], CONFIG['RELATIONS_FOLDER'], CONFIG['UPLOAD_FOLDER'], api_key)
    
    status_2 = task_status.get(task_id_2)
    if status_2 and status_2['status'] == 'completed':
        print("Step 2 Completed Successfully.")
        print(f"Output: {status_2.get('processed_file')}")
    else:
        print(f"Step 2 Failed: {status_2.get('message') if status_2 else 'Unknown error'}")
        return

    # 5. Self Verification
    print("\n--- Step 3: Self Verification ---")
    task_id_3 = str(uuid.uuid4())
    json_filename = os.path.splitext(filename)[0] + '.json'
    self_verification(task_id_3, json_filename, api_key)
    
    status_3 = task_status.get(task_id_3)
    if status_3 and status_3['status'] == 'completed':
        print("Self Verification Completed Successfully.")
        print(status_3.get('message'))
    else:
        print(f"Self Verification Failed: {status_3.get('message') if status_3 else 'Unknown error'}")
        return

    # 6. Convert to IMF
    print("\n--- Step 4: Convert to IMF ---")
    # We'll convert the checked file
    checked_filename = os.path.splitext(filename)[0] + '_checked.json'
    checked_path = os.path.join(CONFIG['SELF_CHECKED_DATA_FOLDER'], checked_filename)
    
    output_imf_name = os.path.splitext(filename)[0] + '_verified.imf'
    output_imf_path = os.path.join(CONFIG['IMF_DATA_FOLDER'], output_imf_name)
    
    try:
        convert_to_imf(checked_path, output_imf_path)
        print(f"IMF Conversion Completed. File saved to: {output_imf_path}")
    except Exception as e:
        print(f"IMF Conversion Failed: {e}")

if __name__ == "__main__":
    main()