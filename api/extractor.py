import os
import json
import pandas as pd
import fitz  # PyMuPDF
from litellm import completion
from concurrent.futures import ThreadPoolExecutor, as_completed


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

    if not text.strip():
        row = {(col.get('name', col) if isinstance(col, dict) else col): f"Empty/Unreadable PDF: {filename}" for col in columns}
        row['Source File'] = filename
        return [row]

    if not api_key:
        row = {(col.get('name', col) if isinstance(col, dict) else col): "Error: Missing OPENAI_API_KEY" for col in columns}
        row['Source File'] = filename
        return [row]

    col_names = [col.get('name', col) if isinstance(col, dict) else col for col in columns]

    prompt = f"""You are an advanced data extraction assistant. You process medical documents (IDR determinations, EOBs, records, etc.).{learning_rules}

Extract ALL records from the document below. Return a JSON object with one key "records" whose value is an array of objects.

Each object must use EXACTLY these keys:
{json.dumps(col_names)}

Extraction logic per field:
{json.dumps(columns, indent=2)}

RULES:
1. A document may contain MULTIPLE records (e.g. multiple Determination blocks). Extract EVERY one — do not stop after the first.
2. Keys must exactly match the field names listed above.
3. Use "N/A" for any value that cannot be found.
4. For the Date field: look for "period begins on", "determination date", or the letter issuance date. Should almost never be N/A.
5. Return ONLY valid JSON — no markdown, no backticks, no commentary.

DOCUMENT TEXT:
{text[:40000]}"""

    try:
        response = completion(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
            temperature=0.1,
            response_format={"type": "json_object"},  # Forces clean JSON — no markdown wrapping
        )
        content = response.choices[0].message.content.strip()
        parsed = json.loads(content)

        # Accept {"records": [...]} wrapper or bare list/dict
        if isinstance(parsed, dict) and "records" in parsed:
            data = parsed["records"]
        elif isinstance(parsed, list):
            data = parsed
        elif isinstance(parsed, dict):
            data = [parsed]
        else:
            data = []

        if not data:
            row = {col_name: "No Data Found" for col_name in col_names}
            row['Source File'] = filename
            return [row]

        results = []
        for item in data:
            clean = {col_name: item.get(col_name, "N/A") for col_name in col_names}
            clean['Source File'] = filename
            results.append(clean)
        return results

    except Exception as e:
        print(f"LLM Extraction Error for {pdf_path}: {e}")
        row = {col_name: f"Extraction Error: {str(e)}" for col_name in col_names}
        row['Source File'] = filename
        return [row]


def process_pdfs_to_excel(pdf_paths: list, columns: list) -> str:
    """
    Process all PDFs in parallel (one thread per PDF) and write a combined Excel file.
    With N files, wall-clock time ≈ time for the slowest single file instead of sum of all.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    learning_rules = get_learning_rules()

    # Cap at 10 concurrent workers to stay within OpenAI rate limits
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

    # Move Source File to the first column
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
