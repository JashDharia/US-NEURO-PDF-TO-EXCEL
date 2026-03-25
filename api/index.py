from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
from typing import List
from pydantic import BaseModel
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from extractor import process_pdfs_to_excel
import uvicorn
import sqlite3
import pandas as pd
from datetime import datetime
import uuid
import hashlib
from io import StringIO

# Initialize Database
DB_PATH = "/tmp/history.db"

def get_db_connection():
    postgres_url = os.environ.get("POSTGRES_URL") or os.environ.get("POSTGRES_PRISMA_URL") or os.environ.get("POSTGRES_URL_NON_POOLING")
    if postgres_url:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(postgres_url)
        return conn, True # True means it's Postgres
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn, False # False means it's SQLite

def init_db():
    conn, is_postgres = get_db_connection()
    cursor = conn.cursor()
    if is_postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extraction_jobs (
                id VARCHAR(255) PRIMARY KEY,
                created_at TIMESTAMP NOT NULL,
                file_names TEXT NOT NULL,
                result_json TEXT NOT NULL
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extraction_jobs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                file_names TEXT NOT NULL,
                result_json TEXT NOT NULL
            )
        ''')
        
    try:
        cursor.execute("ALTER TABLE extraction_jobs ADD COLUMN file_hash TEXT")
    except Exception:
        pass # Column already exists
        
    conn.commit()
    conn.close()

init_db()

class Feedback(BaseModel):
    rule: str

app = FastAPI(title="US Neuro PDF Extractor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "US Neuro Extraction Service is running."}

@app.post("/api/extract")
async def extract_pdfs(
    files: List[UploadFile] = File(...),
    columns: str = Form(...)
):
    valid_files = [f for f in files if f.filename.endswith('.pdf')]
    if not valid_files:
        raise HTTPException(status_code=400, detail="No valid PDF files provided.")
    
    try:
        col_list = json.loads(columns)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid columns format.")
    
    temp_paths = []
    hasher = hashlib.md5()
    
    for file in valid_files:
        content = await file.read()
        hasher.update(content)
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(content)
        temp_paths.append(temp_path)
        
    combined_hash = "v3_" + hasher.hexdigest()
        
    try:
        conn, is_postgres = get_db_connection()
        cursor = conn.cursor()
        
        # Check cache
        if is_postgres:
             cursor.execute("SELECT id, result_json FROM extraction_jobs WHERE file_hash = %s", (combined_hash,))
        else:
             cursor.execute("SELECT id, result_json FROM extraction_jobs WHERE file_hash = ?", (combined_hash,))
             
        cached_row = cursor.fetchone()
        
        if cached_row:
             job_id = cached_row[0] if is_postgres else cached_row["id"]
             result_json = cached_row[1] if is_postgres else cached_row["result_json"]
             
             df = pd.read_json(StringIO(result_json), orient='records')
             
             output_filename = (
                valid_files[0].filename + "_extracted.xlsx"
                if len(valid_files) == 1
                else "US_Neuro_Batch_Extraction.xlsx"
             )
             output_path = f"/tmp/{output_filename}"
             df.to_excel(output_path, index=False)
             
             conn.close()
             return {
                 "status": "success", 
                 "job_id": job_id,
                 "excel_url": f"/api/download?file={output_filename}",
                 "cached": True
             }
             
        # Process the PDFs if no cache hit
        excel_path = process_pdfs_to_excel(temp_paths, col_list)
        
        df = pd.read_excel(excel_path)
        df = df.fillna("N/A") 
        raw_json_str = df.to_json(orient='records')
        
        job_id = str(uuid.uuid4())
        file_names_str = json.dumps([f.filename for f in valid_files])
        current_time = datetime.utcnow().isoformat()
        
        if is_postgres:
            cursor.execute(
                "INSERT INTO extraction_jobs (id, created_at, file_names, result_json, file_hash) VALUES (%s, %s, %s, %s, %s)",
                (job_id, current_time, file_names_str, raw_json_str, combined_hash)
            )
        else:
            cursor.execute(
                "INSERT INTO extraction_jobs (id, created_at, file_names, result_json, file_hash) VALUES (?, ?, ?, ?, ?)",
                (job_id, current_time, file_names_str, raw_json_str, combined_hash)
            )
        conn.commit()
        conn.close()

        return {
            "status": "success", 
            "job_id": job_id,
            "excel_url": f"/api/download?file={os.path.basename(excel_path)}",
            "cached": False
        }
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb)
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}\nTraceback: {tb}")
    finally:
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.remove(temp_path)

@app.get("/api/download")
def download_file(file: str):
    file_path = f"/tmp/{file}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=file)

@app.post("/api/feedback")
def add_feedback(feedback: Feedback):
    if not feedback.rule.strip():
        raise HTTPException(status_code=400, detail="Rule cannot be empty")
        
    rules_path = "/tmp/rules.json"
    rules = []
    if os.path.exists(rules_path):
        with open(rules_path, "r") as f:
            try:
                rules = json.load(f)
            except:
                pass
                
    rules.append({"rule": feedback.rule.strip()})
    
    with open(rules_path, "w") as f:
        json.dump(rules, f, indent=2)
        
    return {"status": "success", "message": "Rule saved."}

@app.get("/api/history")
def get_history():
    conn, is_postgres = get_db_connection()
    if is_postgres:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cursor = conn.cursor()
    # Return without the massive result_json payload
    cursor.execute("SELECT id, created_at, file_names FROM extraction_jobs ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    history_list = []
    for row in rows:
        history_list.append({
            "id": row["id"],
            "created_at": row["created_at"],
            "file_names": json.loads(row["file_names"])
        })
    return {"status": "success", "history": history_list}

@app.get("/api/history/{job_id}")
def get_history_detail(job_id: str):
    conn, is_postgres = get_db_connection()
    if is_postgres:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM extraction_jobs WHERE id = %s", (job_id,))
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM extraction_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return {
        "status": "success",
        "job": {
            "id": row["id"],
            "created_at": row["created_at"],
            "file_names": json.loads(row["file_names"]),
            "data": json.loads(row["result_json"])
        }
    }

@app.post("/api/generate-logic")
async def generate_logic(
    name: str = Form(...),
    file: UploadFile = File(None)
):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Column name cannot be empty")
        
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
         raise HTTPException(status_code=500, detail="OPENAI_API_KEY not found on server")

    from litellm import completion
    from extractor import extract_text_from_pdf
    
    context_text = ""
    if file and file.filename.endswith('.pdf'):
        temp_path = f"/tmp/context_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        try:
            extracted = extract_text_from_pdf(temp_path)
            context_text = extracted[:15000]
        except Exception as e:
            print(f"Context extraction error: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    if context_text:
        prompt = f"""
        You are an AI assistant helping a user extract a specific column named '{name.strip()}' from the following medical document.
        
        Analyze the document text provided below. 
        1. Does information related to '{name.strip()}' exist in this document?
        2. If YES: Write a ONE-SENTENCE concise instruction for another AI data extractor on how to find it. Do not wrap in quotes.
        3. If NO: Reply exactly with this warning: "Warning: Information for '{name.strip()}' does not appear to exist in the provided sample document. Are you sure you want to extract this?"
        
        DOCUMENT TEXT:
        {context_text}
        """
    else:
        prompt = f"Write a one-sentence instruction for an AI data extractor on how to extract the field named '{name.strip()}' from a medical document or EOB. Be concise and clear. Do not wrap in quotes or add prefix text. Just the instruction."
    
    try:
        response = completion(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
            temperature=0.7
        )
        logic = response.choices[0].message.content.strip().strip('"\'')
        return {"status": "success", "logic": logic}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Vercel's @vercel/python runtime detects the `app` variable natively as an ASGI app.
# No Mangum wrapper needed — exposing `app` directly is the correct approach.

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
