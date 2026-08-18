import sys
import traceback
from pathlib import Path
from backend.config.database import _get_session_factory
from ingestion.service import IngestionService

failed_pdfs = ["2005.11401.pdf", "2303.08774.pdf", "2309.00267.pdf", "2402.01990.pdf"]
SessionLocal = _get_session_factory()
service = IngestionService()

for filename in failed_pdfs:
    path = Path(f"data/test_corpus/{filename}")
    if not path.exists():
        print(f"File not found: {path}")
        continue
    
    print(f"==================================================")
    print(f"TESTING {filename}")
    print(f"==================================================")
    try:
        content = path.read_bytes()
        with SessionLocal() as db:
            paper, parsed, chunk_count = service.ingest(db, content, filename)
            print("SUCCESS unexpectedly!")
    except Exception as e:
        print("EXCEPTION CAUGHT:")
        traceback.print_exc()
