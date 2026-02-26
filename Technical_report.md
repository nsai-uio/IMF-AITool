# Technical Report: Information Modelling Framework (IMF) AI tool

##  1. Introduction
This software is a Flask-based web application designed to automate the extraction, verification, and modelling of system information from industrial documents (PDFs) using Generative AI. Moreover, it provides a chat window for users to query about IMF knowledge and industrial documents.

**Methods**
The core method used in this application for information extraction, modelling, verification, and chat window is In-Context Learning (ICL). Specifically, it leverages techniques including task instruction prompting, Chain-of-Thought (CoT), and Few-shot prompting. ICL provides a training-free approach and eliminates the computationally expensive step of fine-tuning.

## 2. Application Overview

This Application is a tool for assisting system engineers to convert unstructured technical specifications (PDFs) into structured Information Models. By following the steps in the application, users can learn and explore how AI can assist in modelling system information.

**What can it do?**
1.  **System Component Extraction**: Parses PDF text to identify system components and their hierarchical structure (```partOf```).
2.  **Relation Extraction**: Identifies complex relationships of components, including functional allocations (`fulfills`), physical connections (`connectedTo`), and interfaces (`hasTerminal`).
3.  **Self-Verification**: Implements a verification process where the AI generates claims based on extracted relations and verifies them against the original document to reduce hallucinations.
4.  **Visualize as Graphs**:
Visualize intermediate and final reasults as knowledge graphs.
4.  **IMF Conversion**: Converts previouly generated reasults (JSON) into an IMF format, calculating layout coordinates for visualization nodes and edges in the IMF editor.
5.  **Contextual Chat**: Provides a chat interface allowing users to query the uploaded document or the IMF Manual.
6.  **Custom Export**: Allows users to filter and export specific relations to customize the model.

## 3. System Architecture
The application is built on a lightweight, modular architecture:
*   **Core Framework**: Python Flask serves as the backend web server.
*   **AI Engine**: Google Generative AI (`gemini-2.5-pro`) handles NLP tasks.
*   **Task Management**: Asynchronous background threading is used for long-running AI tasks (extraction and verification) to ensure UI responsiveness.
*   **Data Persistence**: A file-system-based approach manages uploads, intermediate JSON results, and logs.

## 4. Component Summary
The following table summarizes the key backend components and the frontend elements that interact with them.

| Category | Element | Type | Description |
| :--- | :--- | :--- | :--- |
| **Backend** | `app` | Flask Instance | The central application object handling configuration, routing, and session management. |
| **Backend** | `extract_components_task` | Background Task | **Step 1**: Extracts text from PDF and uses LLM to generate a hierarchical JSON dictionary of system components and subcomponents. |
| **Backend** | `extract_relations_task` | Background Task | **Step 2**: Analyzes text and components to determine relations (tagID, partOf, fulfills, hasTerminal, connectedTo). |
| **Backend** | `self_check_task` | Background Task | **Step 3**: Generates verification claims from the extracted data and validates them against the source PDF. |
| **Backend** | `convert_json_to_imf` | Utility Function | Converts structured JSON into IMF format (Nodes/Edges) with an auto-layout algorithm. |
| **Backend** | `parse_json` | Utility Function | A robust parser designed to clean, handle, and repair potentially malformed JSON output returned by the LLM. |
| **Backend** | `/validate_api_key` | API Endpoint | Validates the Google API Key and stores it in the user session. |
| **Backend** | `/chat` | API Endpoint | Handles user queries by injecting document context and IMF manual text into the LLM prompt. |
| **Backend** | `/status/<task_id>` | API Endpoint | Returns the current status (processing, completed, error) and progress percentage of background tasks. |
| **Backend** | `/list_processed_files` | API Endpoint | Retrieves a list of all successfully processed JSON files available for visualization or querying. |
| &nbsp; | &nbsp; | &nbsp; | &nbsp; |
| **Frontend** | `validateApiKey()` | JS Function | Sends the user's API key to the `/validate_api_key` endpoint and updates the UI (enabling buttons/removing inputs) based on the validation result.|
| **Frontend** | `removeApiKey()` | JS Function | Sends a POST request to `/remove_api_key` to clear the active key, disables all action buttons, clears the chat and the visual graph. |
| **Frontend** | `pollTaskStatus()` | JS Function | Periodically polls the `/status/<task_id>` endpoint using setInterval to update UI text and progress indicators dynamically. |
| **Frontend** | `refreshFileList()` | JS Function | Fetches available document names from `/list_processed_files` and populates the `#fileSelect` dropdown element. |
| **Frontend** | `sendQuestion()` | JS Function | Captures user queries from the `#chat-input`, posts them to the `/chat endpoint`, and appends the AI's response to the `#chat-history` window. |
| **Frontend** | `cytoscape` & `#cy` | JS Library / UI Container | Consumes the processed JSON data (Nodes/Edges) representing the system information model and renders it as an interactive visual graph.|

## 5. Technical Implementation Details

### 5.1 Asynchronous Processing
Due to the latency of Large Language Model (LLM) inference, the application uses `threading` package.
*   When a request is received (e.g., `/step1_components`), a unique `task_id` is generated.
*   A new thread is spawned to run the processing function.
*   The main thread returns the `task_id` immediately.
*   The client polls `/status/<task_id>` to update the UI.

### 5.2 Data Flow & Transformation
1.  **PDF Upload**: Saved to `uploads/`.
2.  **Text Extraction**: `PyPDF2` extracts raw text from PDF files.
3.  **LLM Processing**:
    *   *Prompting*: Custom prompts inject the raw text and specific instructions.
    *   *Parsing*: The `parse_json` function uses Regex to clean common LLM JSON formatting errors (missing commas, trailing commas).
4.  **IMF Generation**:
    *   The `convert_json_to_imf` function maps the generated model to a imf file.
    *   It calculates `subtree_width` to position nodes hierarchically without overlap.
    *   It creates "Function" nodes and "Product" nodes, linking them via "fulfilled" edges.

### 5.3 Security & Configuration
*   **API Keys**: Google API keys are configured on-demand per session or loaded from `.env` for local testing.
*   **File Safety**: `werkzeug.utils.secure_filename` is used to prevent directory traversal attacks via file uploads.
*   **Session**: `app.secret_key` is generated using `os.urandom(24)` for secure session signing.

## 6. Dependencies
*   **Flask**: Web Server Gateway Interface.
*   **google-generativeai**: SDK for accessing Gemini models.
*   **PyPDF2**: Library for reading PDF files.
*   **python-dotenv**: Loads environment variables.
*   **Werkzeug**: WSGI utility library.