import os
import json
import pandas as pd
import fitz  # PyMuPDF
from litellm import completion

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from the uploaded PDF using specialized layout preservation to prevent missing data."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            # Using get_text("blocks") or simply layout dict for better structure
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (b[1], b[0])) # Sort top-to-bottom, left-to-right
            for b in blocks:
                # b[4] is the text content
                if b[4].strip():
                    text += b[4] + "\n"
        return text
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return ""


def get_learning_rules() -> str:
    rules_path = "rules.json"
    if not os.path.exists(rules_path):
        return ""
    try:
        with open(rules_path, "r") as f:
            rules = json.load(f)
            if not rules:
                return ""
            rule_texts = "\n".join([f"- {r['rule']}" for r in rules])
            return f"\n\nCRITICAL AI LEARNING RULES (Apply to ALL extraction):\n{rule_texts}"
    except Exception as e:
        print(f"Error loading rules: {e}")
        return ""

def process_pdfs_to_excel(pdf_paths: list, columns: list) -> str:
    """
    Reads multiple PDFs, asks LLM to extract 'columns', and saves to a combined Excel.
    """
    all_extracted_data = []
    
    # Check if API key exists
    api_key = os.environ.get("OPENAI_API_KEY")
    
    for pdf_path in pdf_paths:
        text = extract_text_from_pdf(pdf_path)
        
        if not text.strip():
            all_extracted_data.append({col.get('name', col) if isinstance(col, dict) else col: f"Empty/Unreadable PDF: {os.path.basename(pdf_path)}" for col in columns})
            continue

        if not api_key:
            print("Error: OPENAI_API_KEY not set.")
            all_extracted_data.append({col.get('name', col) if isinstance(col, dict) else col: "Error: Missing OPENAI_API_KEY" for col in columns})
            continue

        learning_rules = get_learning_rules()

        prompt = f"""
        You are an advanced data extraction assistant. You process various document types (IDR determinations, EOBs, medical records, etc.).{learning_rules}
        
        Extract the requested data points from the text below based strictly on the provided logic.
        Each requested field has a 'name' (the column header) and 'logic' (instructions on how to find/format it):
        {json.dumps(columns, indent=2)}
        
        CRITICAL INSTRUCTIONS:
        1. A single document might contain MULTIPLE distinct records (e.g., multiple "Determinations", multiple claims). You MUST extract EVERY SINGLE ONE.
        2. Specifically for IDR documents, read every single page to ensure you do not miss any "Determination X" blocks. Do not stop after the first few.
        3. You MUST return ONLY a JSON ARRAY of objects (`[ {{...}}, {{...}} ]`). 
        4. If there is only one record, return an array with one object (`[ {{...}} ]`).
        5. For the 'Date' field, look for "period begins on", "determination date", or the date the letter was issued. It should NEVER be 'N/A' if a date exists anywhere in the text.
        6. The keys of the JSON objects MUST exactly match the 'name' properties from the instructions above.
        7. If a column value is missing from the text for a specific record, output 'N/A' or an empty string.
        8. Do not include markdown formatting or backticks around the JSON. Look closely at the entire document.
        
        TEXT:
        {text[:40000]} # Limit text slightly to prevent extreme context overflow, but large enough for most medical documents.
        """
        
        try:
            response = completion(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                api_key=api_key,
                temperature=0.1
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
                
            data = json.loads(content)
            
            # Ensure it resolves to a list even if the LLM messed up and returned a dict
            if isinstance(data, dict):
                data = [data]
            elif not isinstance(data, list):
                data = []

            if len(data) == 0:
                fallback = {col.get('name', col) if isinstance(col, dict) else col: "No Data Found" for col in columns}
                fallback['Source File'] = os.path.basename(pdf_path)
                all_extracted_data.append(fallback)
            else:
                for item in data:
                    # Sanitize keys just in case
                    clean_item = {}
                    for col in columns:
                        col_name = col.get('name', col) if isinstance(col, dict) else col
                        clean_item[col_name] = item.get(col_name, "N/A")
                    clean_item['Source File'] = os.path.basename(pdf_path)
                    all_extracted_data.append(clean_item)

        except Exception as e:
            print(f"LLM Extraction Error for {pdf_path}: {e}")
            fallback_row = {col.get('name', col) if isinstance(col, dict) else col: "Extraction Error" for col in columns}
            fallback_row['Source File'] = os.path.basename(pdf_path)
            all_extracted_data.append(fallback_row)

    # Create Excel using Pandas
    df = pd.DataFrame(all_extracted_data)
    
    # Reorder columns to have Source File at the very beginning
    cols = df.columns.tolist()
    if 'Source File' in cols:
        cols.insert(0, cols.pop(cols.index('Source File')))
        df = df[cols]
    
    output_filename = "US_Neuro_Batch_Extraction.xlsx"
    if len(pdf_paths) == 1:
        output_filename = os.path.basename(pdf_paths[0]) + "_extracted.xlsx"
        
    output_path = f"/tmp/{output_filename}"
    df.to_excel(output_path, index=False)
    
    return output_path
