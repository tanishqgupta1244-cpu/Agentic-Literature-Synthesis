import httpx
import os
import sys
import tempfile
import urllib.request
import psycopg
from time import sleep

API_URL = "http://localhost:8000/papers/upload"
DB_URL = "postgresql://reviewer:password@localhost:5432/literature_review_dev"
CORPUS_DIR = "data/test_corpus"

os.makedirs(CORPUS_DIR, exist_ok=True)

arxiv_ids_smoke = ["1706.03762", "2005.11401", "2103.00020"]
arxiv_ids_corpus = [
    "2303.08774", "2304.03442", "2305.10601", "2306.02707", "2307.09288",
    "2308.10792", "2309.00267", "2310.06825", "2311.01606", "2312.00752",
    "2401.04088", "2402.01990", "2403.05530", "2404.07143", "2405.00332"
]

def download_paper(arxiv_id):
    path = os.path.join(CORPUS_DIR, f"{arxiv_id}.pdf")
    if not os.path.exists(path):
        print(f"Downloading {arxiv_id}...")
        try:
            req = urllib.request.Request(f"https://arxiv.org/pdf/{arxiv_id}.pdf", headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                with open(path, 'wb') as f:
                    f.write(response.read())
            sleep(2)  # be nice to arxiv
        except Exception as e:
            print(f"Failed to download {arxiv_id}: {e}")
            return None
    return path

def upload_paper(path):
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        files = {"file": (filename, f, "application/pdf")}
        response = httpx.post(API_URL, files=files, timeout=60.0)
    return response

def check_db():
    try:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM papers;")
                papers = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM chunks;")
                chunks = cur.fetchone()[0]
                return papers, chunks
    except Exception as e:
        print(f"DB Error: {e}")
        return 0, 0

def main():
    print("=== SMOKE TEST ===")
    smoke_paths = [download_paper(i) for i in arxiv_ids_smoke]
    smoke_paths = [p for p in smoke_paths if p]
    
    for path in smoke_paths:
        print(f"Uploading {path}...")
        r = upload_paper(path)
        print(f"Status: {r.status_code}")
        if r.status_code != 201:
            print(r.text)
            
    p, c = check_db()
    print(f"DB Status after smoke: {p} papers, {c} chunks")
    
    print("=== TEST ROLLBACK / INVALID PDF ===")
    with open("invalid.pdf", "w") as f:
        f.write("This is not a pdf.")
    r = upload_paper("invalid.pdf")
    print(f"Invalid upload status: {r.status_code}")
    os.remove("invalid.pdf")
    p2, c2 = check_db()
    if p2 == p and c2 == c:
        print("Rollback successful: no orphaned records added.")
    else:
        print("Rollback failed! Records changed.")
        
    print("=== INITIAL 15-PAPER CORPUS ===")
    corpus_paths = [download_paper(i) for i in arxiv_ids_corpus]
    corpus_paths = [p for p in corpus_paths if p]
    
    print("\npaper | pages | chunks | status | error(if any)")
    print("-" * 60)
    
    for path in corpus_paths:
        r = upload_paper(path)
        if r.status_code == 201:
            data = r.json()
            paper = data.get("paper", {})
            status = "SUCCESS"
            error = ""
            pages = paper.get("page_count", 0)
            chunk_cnt = len(data.get("chunks", []))
            filename = paper.get("filename", os.path.basename(path))
        else:
            status = "FAILED"
            error = r.text[:50]
            pages = "?"
            chunk_cnt = "?"
            filename = os.path.basename(path)
            
        print(f"{filename} | {pages} | {chunk_cnt} | {status} | {error}")
        
    p_final, c_final = check_db()
    print(f"\nFinal DB Status: {p_final} papers, {c_final} chunks")

if __name__ == "__main__":
    main()
