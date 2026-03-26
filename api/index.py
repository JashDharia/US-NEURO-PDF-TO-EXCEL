from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

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


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

DB_PATH = "/tmp/history.db"


def get_db_connection():
    """Return (conn, is_postgres). Prefers Postgres when env vars are present."""
    postgres_url = (
        os.environ.get("POSTGRES_URL")
        or os.environ.get("POSTGRES_PRISMA_URL")
        or os.environ.get("POSTGRES_URL_NON_POOLING")
    )
    if postgres_url:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(postgres_url)
        return conn, True
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn, False


def init_db():
    """Create tables and migrate schema (idempotent)."""
    conn, is_postgres = get_db_connection()
    cursor = conn.cursor()

    if is_postgres:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extraction_jobs (
                id            VARCHAR(255) PRIMARY KEY,
                created_at    TIMESTAMP    NOT NULL,
                file_names    TEXT         NOT NULL,
                result_json   TEXT         NOT NULL,
                file_hash     TEXT,
                total_tokens  INTEGER      DEFAULT 0,
                total_cost    DOUBLE PRECISION DEFAULT 0.0
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extraction_jobs (
                id           TEXT    PRIMARY KEY,
                created_at   TEXT    NOT NULL,
                file_names   TEXT    NOT NULL,
                result_json  TEXT    NOT NULL,
                file_hash    TEXT,
                total_tokens INTEGER DEFAULT 0,
                total_cost   REAL    DEFAULT 0.0
            )
        ''')

    # Safe migrations for existing databases
    for col, definition in [
        ("file_hash",    "TEXT"),
        ("total_tokens", "INTEGER DEFAULT 0"),
        ("total_cost",   "REAL DEFAULT 0.0"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE extraction_jobs ADD COLUMN {col} {definition}")
        except Exception:
            pass  # Column already exists

    conn.commit()
    conn.close()


init_db()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# /api/extract
# ---------------------------------------------------------------------------

@app.post("/api/extract")
async def extract_pdfs(
    files: List[UploadFile] = File(...),
    columns: str = Form(...),
):
    valid_files = [f for f in files if f.filename.endswith('.pdf')]
    if not valid_files:
        raise HTTPException(status_code=400, detail="No valid PDF files provided.")

    try:
        col_list = json.loads(columns)
    except Exception:
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

    # Version prefix forces re-extraction when extractor logic changes
    combined_hash = "v8_" + hasher.hexdigest()

    try:
        conn, is_postgres = get_db_connection()
        cursor = conn.cursor()

        # Cache check
        if is_postgres:
            cursor.execute(
                "SELECT id, result_json, total_tokens, total_cost "
                "FROM extraction_jobs WHERE file_hash = %s",
                (combined_hash,),
            )
        else:
            cursor.execute(
                "SELECT id, result_json, total_tokens, total_cost "
                "FROM extraction_jobs WHERE file_hash = ?",
                (combined_hash,),
            )

        cached_row = cursor.fetchone()

        if cached_row:
            job_id      = cached_row[0] if is_postgres else cached_row["id"]
            result_json = cached_row[1] if is_postgres else cached_row["result_json"]
            ttokens     = int(cached_row[2]   if is_postgres else cached_row["total_tokens"] or 0)
            tcost       = float(cached_row[3] if is_postgres else cached_row["total_cost"]   or 0.0)

            df = pd.read_json(StringIO(result_json), orient='records', convert_dates=False)
            output_filename = (
                valid_files[0].filename + "_extracted.xlsx"
                if len(valid_files) == 1
                else "US_Neuro_Batch_Extraction.xlsx"
            )
            output_path = f"/tmp/{output_filename}"
            df.to_excel(output_path, index=False)
            conn.close()

            return {
                "status":       "success",
                "job_id":       job_id,
                "excel_url":    f"/api/download?file={output_filename}",
                "cached":       True,
                "total_tokens": ttokens,
                "total_cost":   round(tcost, 6),
            }

        # Fresh extraction
        excel_path, grand_tokens, grand_cost = process_pdfs_to_excel(temp_paths, col_list)

        df = pd.read_excel(excel_path)
        df = df.fillna("N/A")
        raw_json_str = df.to_json(orient='records')

        job_id = str(uuid.uuid4())
        file_names_str = json.dumps([f.filename for f in valid_files])
        current_time = datetime.utcnow().isoformat()

        if is_postgres:
            cursor.execute(
                "INSERT INTO extraction_jobs "
                "(id, created_at, file_names, result_json, file_hash, total_tokens, total_cost) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (job_id, current_time, file_names_str, raw_json_str,
                 combined_hash, grand_tokens, grand_cost),
            )
        else:
            cursor.execute(
                "INSERT INTO extraction_jobs "
                "(id, created_at, file_names, result_json, file_hash, total_tokens, total_cost) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, current_time, file_names_str, raw_json_str,
                 combined_hash, grand_tokens, grand_cost),
            )
        conn.commit()
        conn.close()

        return {
            "status":       "success",
            "job_id":       job_id,
            "excel_url":    f"/api/download?file={os.path.basename(excel_path)}",
            "cached":       False,
            "total_tokens": grand_tokens,
            "total_cost":   round(grand_cost, 6),
        }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb)
        with open("/tmp/error.log", "w") as f:
            f.write(tb)
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}\nTraceback: {tb}")

    finally:
        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ---------------------------------------------------------------------------
# /api/download
# ---------------------------------------------------------------------------

@app.get("/api/download")
def download_file(file: str):
    file_path = f"/tmp/{file}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file,
    )


# ---------------------------------------------------------------------------
# /api/feedback
# ---------------------------------------------------------------------------

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
            except Exception:
                pass

    rules.append({"rule": feedback.rule.strip()})
    with open(rules_path, "w") as f:
        json.dump(rules, f, indent=2)

    return {"status": "success", "message": "Rule saved."}


# ---------------------------------------------------------------------------
# /api/history  &  /api/history/{job_id}
# ---------------------------------------------------------------------------

@app.get("/api/history")
def get_history():
    conn, is_postgres = get_db_connection()
    if is_postgres:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cursor = conn.cursor()

    cursor.execute(
        "SELECT id, created_at, file_names, total_tokens, total_cost "
        "FROM extraction_jobs ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()

    history_list = []
    for row in rows:
        history_list.append({
            "id":           row["id"],
            "created_at":   row["created_at"],
            "file_names":   json.loads(row["file_names"]),
            "total_tokens": int(row["total_tokens"]   or 0),
            "total_cost":   round(float(row["total_cost"] or 0.0), 6),
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
            "id":           row["id"],
            "created_at":   row["created_at"],
            "file_names":   json.loads(row["file_names"]),
            "data":         json.loads(row["result_json"]),
            "total_tokens": int(row["total_tokens"]   or 0),
            "total_cost":   round(float(row["total_cost"] or 0.0), 6),
        },
    }


# ---------------------------------------------------------------------------
# /api/stats  — aggregate token + cost across ALL jobs
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def get_stats():
    """Cumulative token usage and cost across every extraction job."""
    conn, is_postgres = get_db_connection()
    if is_postgres:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cursor = conn.cursor()

    cursor.execute(
        "SELECT "
        "  COUNT(*)                    AS job_count, "
        "  COALESCE(SUM(total_tokens), 0) AS lifetime_tokens, "
        "  COALESCE(SUM(total_cost),   0) AS lifetime_cost "
        "FROM extraction_jobs"
    )
    row = cursor.fetchone()
    conn.close()

    return {
        "status": "success",
        "stats": {
            "job_count":       int(row["job_count"]       or 0),
            "lifetime_tokens": int(row["lifetime_tokens"] or 0),
            "lifetime_cost":   round(float(row["lifetime_cost"] or 0.0), 6),
        },
    }


# ---------------------------------------------------------------------------
# /api/generate-logic
# ---------------------------------------------------------------------------

@app.post("/api/generate-logic")
async def generate_logic(
    name: str = Form(...),
    file: UploadFile = File(None),
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
            context_text = extracted[:15_000]
        except Exception as e:
            print(f"Context extraction error: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    if context_text:
        prompt = (
            f"You are an AI assistant helping a user extract a specific column named '{name.strip()}' "
            "from the following medical document.\n\n"
            f"1. Does information related to '{name.strip()}' exist in this document?\n"
            "2. If YES: Write a ONE-SENTENCE concise instruction for another AI data extractor on how to "
            "find it. Do not wrap in quotes.\n"
            f"3. If NO: Reply exactly with: \"Warning: Information for '{name.strip()}' does not appear "
            "to exist in the provided sample document. Are you sure you want to extract this?\"\n\n"
            f"DOCUMENT TEXT:\n{context_text}"
        )
    else:
        prompt = (
            f"Write a one-sentence instruction for an AI data extractor on how to extract the field "
            f"named '{name.strip()}' from a medical document or EOB. "
            "Be concise and clear. Do not wrap in quotes or add prefix text. Just the instruction."
        )

    try:
        response = completion(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key,
            temperature=0.7,
        )
        logic = response.choices[0].message.content.strip().strip('"\'')
        return {"status": "success", "logic": logic}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Entry point (local dev only — Vercel uses the `app` ASGI object directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
