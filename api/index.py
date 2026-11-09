import os
import sys
import shutil
import tempfile
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Top-level application assignment for Vercel AST entrypoint detection
app = FastAPI(
    title="RetailIQ – AI-Powered Inventory Intelligence",
    description="Intelligent Inventory Monitoring and Automated Replenishment Agent",
    version="1.0.0"
)

# Standard handler alias recognized by Vercel Python runtime
handler = app

# Enable CORS for local development and hosted domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

for path in [CURRENT_DIR, PARENT_DIR, os.path.join(CURRENT_DIR, "backend"), os.path.join(PARENT_DIR, "backend")]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

# Seed database into writable /tmp for Vercel serverless environment
is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
if is_serverless:
    tmp_dir = "/tmp" if os.path.exists("/tmp") else tempfile.gettempdir()
    target_db = os.path.join(tmp_dir, "retailiq.db")
    
    candidates = [
        os.path.join(CURRENT_DIR, "data", "retailiq.db"),
        os.path.join(CURRENT_DIR, "retailiq.db"),
        os.path.join(PARENT_DIR, "data", "retailiq.db"),
        os.path.join(PARENT_DIR, "backend", "data", "retailiq.db"),
        os.path.join(CURRENT_DIR, "backend", "data", "retailiq.db"),
    ]
    
    src_db = None
    for c in candidates:
        if os.path.exists(c) and os.path.getsize(c) > 0:
            src_db = c
            break
            
    if src_db:
        if not os.path.exists(target_db) or os.path.getsize(target_db) == 0:
            try:
                shutil.copyfile(src_db, target_db)
                print(f"[Vercel Init] Seeded database from {src_db} ({os.path.getsize(src_db):,} bytes) to {target_db}")
            except Exception as e:
                print(f"[Vercel Init Warning] Failed to copy db: {e}")
                
    if os.path.exists(target_db) and os.path.getsize(target_db) > 0:
        os.environ["DATABASE_URL"] = f"sqlite:///{target_db}"
    elif src_db:
        os.environ["DATABASE_URL"] = f"sqlite:///{src_db}"

# Register core endpoints on both /api and root prefixes
try:
    try:
        from backend.app.api.endpoints import router as api_router
    except ImportError:
        from app.api.endpoints import router as api_router
    
    app.include_router(api_router, prefix="/api")
    app.include_router(api_router)
except Exception as e:
    import traceback
    err_msg = traceback.format_exc()
    print(f"[RetailIQ Router Registration Warning]: {err_msg}")
    
    @app.get("/api/health")
    @app.get("/health")
    def fallback_health():
        return {"status": "degraded", "error": str(e), "traceback": err_msg}

@app.on_event("startup")
def startup_event():
    try:
        try:
            from backend.app.models.database import engine, Base
            from backend.app.models.entities import Product
            from sqlalchemy import inspect
        except ImportError:
            from app.models.database import engine, Base
            from app.models.entities import Product
            from sqlalchemy import inspect
            
        inspector = inspect(engine)
        if not inspector.has_table("products"):
            Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[RetailIQ Startup] Schema note: {e}")
