import os
import json
import base64
import re
import pandas as pd
import fitz  # PyMuPDF
from litellm import completion, completion_cost
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import ThreadPoolExecutor, as_completed


def extract_images_from_pdf(pdf_path: str) -> list:
    """Extract pages as base64 images for OCR."""
    images = []
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom
            img_bytes = pix.tobytes("jpeg")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            images.append(b64)
        return images
    except Exception as e:
        print(f"Error converting PDF to images {pdf_path}: {e}")
        return []


def extract_regex_patterns(text: str) -> dict:
    """Extract common fields using regex to reduce LLM workload and hallucinations."""
    found_data = {}
    npi_match = re.search(r'\b(?:NPI|Provider NPI)[^\d]{0,5}(\d{10})\b', text, re.IGNORECASE)
    if npi_match: found_data["NPI"] = npi_match.group(1)
    
    claim_match = re.search(r'\b(?:Claim|Case)[^\w]{0,10}([A-Z0-9]{5,15})\b', text, re.IGNORECASE)
    if claim_match: found_data["Claim ID"] = claim_match.group(1)
    
    return found_data


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF preserving reading order (top-to-bottom, left-to-right)."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (b[1], b[0]))
            for b in blocks:
                if b[4].strip():
                    text += b[4] + "\n"
        return text
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return ""


def get_learning_rules() -> str:
    rules_path = "/tmp/rules.json"
    if not os.path.exists(rules_path):
        return ""
    try:
        with open(rules_path, "r") as f:
            rules = json.load(f)
            if not rules:
                return ""
            rule_texts = "\n".join([f"- {r['rule']}" for r in rules])
            return f"\n\nCRITICAL AI LEARNING RULES (apply to ALL extraction):\n{rule_texts}"
    except Exception as e:
        print(f"Error loading rules: {e}")
        return ""


def process_single_pdf(pdf_path: str, columns: list, api_key: str, learning_rules: str) -> list:
    """Extract all records from a single PDF. Returns a list of row dicts."""
    filename = os.path.basename(pdf_path)
    text = extract_text_from_pdf(pdf_path)
    
    is_scanned = False
    page_count = 1
    # If very little text is found compared to page count, assume scanned
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        if len(text.strip()) < page_count * 50:
            is_scanned = True
        doc.close()
    except:
        pass
        
    # Ensure gpt-4o-mini is always preferred to guarantee sub-$0.0005 cost
    selected_model = "gpt-4o-mini"
        
    images = []
    if is_scanned:
        images = extract_images_from_pdf(pdf_path)

    if not text.strip() and not images:
        row = {(col.get('name', col) if isinstance(col, dict) else col): f"Empty/Unreadable PDF: {filename}" for col in columns}
        row['Source File'] = filename
        return [row]

    if not api_key:
        row = {(col.get('name', col) if isinstance(col, dict) else col): "Error: Missing OPENAI_API_KEY" for col in columns}
        row['Source File'] = filename
        return [row]

    regex_hints = {}
    if not is_scanned and text:
        regex_hints = extract_regex_patterns(text)
        
        # AGGRESSIVE TOKEN OPTIMIZATION: Paragraph Filtering WITH Date Preservation
        # Skip filtering entirely for standard 1-4 page docs; 12,000 chars natively costs < $0.0004!
        if len(text) > 12000:
            keywords = [col.get('name', col).lower() if isinstance(col, dict) else col.lower() for col in columns]
            keywords.extend(['offer', 'determination', 'idr', 'npi', 'date', 'amount', 'decision', 'patient', 'claim', 'dob', 'dos'])
            
            # Regex to catch ANY date pattern to prevent N/A (e.g. 01/01/2024 or Jan 1, 2024)
            date_pattern = re.compile(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2},? \d{4}\b', re.IGNORECASE)
            
            # Regex to catch Determination Numbers like DISP-1234 or D-5678 to prevent N/A
            det_pattern = re.compile(r'\b(?:disp|det|determination|number)\s*[-#:]?\s*([a-z0-9-]{6,})\b', re.IGNORECASE)
            
            paragraphs = text.replace('\r', '').split('\n\n')
            if len(paragraphs) < 5:
                paragraphs = text.split('\n')
                
            filtered_paragraphs = []
            for p in paragraphs:
                # Always keep short structural lines (headers), lines containing keywords, ANY date, or det ID
                if len(p.strip()) < 100 or date_pattern.search(p) or det_pattern.search(p) or any(k in p.lower() for k in keywords):
                    filtered_paragraphs.append(p)
                    
            filtered_text = "\n".join(filtered_paragraphs)
            
            if len(filtered_text) > 500 and len(filtered_text) < len(text):
                text = filtered_text

    col_names = [col.get('name', col) if isinstance(col, dict) else col for col in columns]

    prompt_instructions = f"""You are an advanced data extraction assistant. You process medical documents (IDR determinations, EOBs, records, etc.).{learning_rules}

Extract ALL records from the document below. Return a JSON object with one key "records" whose value is an array of objects.

Each object must use EXACTLY these keys:
{json.dumps(col_names)}

Extraction logic per field:
{json.dumps(columns, indent=2)}

RULES:
1. Extract EVERY record (e.g., multiple Determination blocks/line items) — do not stop after the first.
2. 🚨 CRITICAL DATE RULE 🚨: Find the single global "Date" (e.g. letter issuance date, determination date) at the top of the document. You MUST copy this EXACT Date into EVERY single line item record's "Date" field. DO NOT put "N/A" for Date on some rows and a Date on one row. EVERY row MUST have the Date.
3. 🚨 DETERMINATION NUMBER RULE 🚨: If the document is a single determination, the Determination Number is "1". If there are multiple line items, number them sequentially "1", "2", "3", etc. NEVER put "N/A" for Determination Number!
4. Do NOT create a weird isolated extra row just for global header data. 
5. Keys must exactly match the field names listed above. Use "N/A" for any missing value.
6. Return ONLY valid JSON — no markdown, no backticks, no commentary."""

    if regex_hints:
         prompt_instructions += f"\n\nPRE-EXTRACTED HIGH-CONFIDENCE FIELDS (Use these if they match your requested fields):\n{json.dumps(regex_hints, indent=2)}"

    chunk_results = []
    total_tokens = 0
    total_cost = 0.0
    
    if is_scanned and images:
        content_array = [{"type": "text", "text": prompt_instructions}]
        for b64_img in images[:4]: # VERCEL TIMEOUT PREVENT: Limit to 4 pages to stay under 10 seconds
            content_array.append({
                "type": "image_url", 
                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
            })
        messages = [{"role": "user", "content": content_array}]
        
        try:
            response = completion(
                model=selected_model,
                messages=messages,
                api_key=api_key,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            if hasattr(response, 'usage') and response.usage:
                total_tokens += response.usage.total_tokens
            try:
                total_cost += completion_cost(completion_response=response)
            except:
                pass
                
            content = response.choices[0].message.content.strip()
            chunk_results.extend(_parse_llm_json(content))
        except Exception as e:
            print(f"Vision API Error: {e}")
            
    else:
        # VERCEL TIMEOUT PREVENT: Limit to exactly ONE API call per document to stay under 10 seconds.
        # Since we already heavily paragraph-filtered the text above, we aggressively pass the pure, filtered document into a single LLM call.
        chunk = text
            
        full_text_prompt = f"{prompt_instructions}\n\nDOCUMENT TEXT:\n{chunk}"
        messages = [{"role": "user", "content": full_text_prompt}]
        try:
            response = completion(
                model=selected_model,
                messages=messages,
                api_key=api_key,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            if hasattr(response, 'usage') and response.usage:
                total_tokens += response.usage.total_tokens
            try:
                total_cost += completion_cost(completion_response=response)
            except:
                pass
            content = response.choices[0].message.content.strip()
            chunk_results.extend(_parse_llm_json(content))
        except Exception as e:
            print(f"LLM Chunk Error: {e}")

    if not chunk_results:
        row = {col_name: "No Data Found or Error" for col_name in col_names}
        row['Source File'] = filename
        return [row]

    # Clean and format results
    results = []
    for item in chunk_results:
        clean = {col_name: item.get(col_name, "N/A") for col_name in col_names}
        clean['Source File'] = filename
        clean['Tokens Used'] = total_tokens
        clean['Est. Cost ($)'] = round(total_cost, 4)
        results.append(clean)
    return results

def _parse_llm_json(content: str) -> list:
    """Helper to parse JSON from LLM into a list of dicts."""
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "records" in parsed:
            return parsed["records"]
        elif isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            return [parsed]
        return []
    except:
        return []


def process_pdfs_to_excel(pdf_paths: list, columns: list) -> str:
    """
    Process all PDFs in parallel (one thread per PDF) and write a combined Excel file.
    Wall-clock time ≈ time for the slowest single file instead of sum of all.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    learning_rules = get_learning_rules()

    max_workers = min(len(pdf_paths), 10)
    results_by_index: dict[int, list] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(process_single_pdf, path, columns, api_key, learning_rules): i
            for i, path in enumerate(pdf_paths)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results_by_index[idx] = future.result()
            except Exception as e:
                filename = os.path.basename(pdf_paths[idx])
                col_names = [col.get('name', col) if isinstance(col, dict) else col for col in columns]
                row = {col_name: f"Error: {str(e)}" for col_name in col_names}
                row['Source File'] = filename
                results_by_index[idx] = [row]

    # Reassemble rows in original file order
    all_extracted_data = []
    for i in sorted(results_by_index.keys()):
        all_extracted_data.extend(results_by_index[i])

    df = pd.DataFrame(all_extracted_data)

    cols = df.columns.tolist()
    if 'Source File' in cols:
        cols.insert(0, cols.pop(cols.index('Source File')))
        df = df[cols]

    output_filename = (
        os.path.basename(pdf_paths[0]) + "_extracted.xlsx"
        if len(pdf_paths) == 1
        else "US_Neuro_Batch_Extraction.xlsx"
    )
    output_path = f"/tmp/{output_filename}"
    df.to_excel(output_path, index=False)
    return output_path
