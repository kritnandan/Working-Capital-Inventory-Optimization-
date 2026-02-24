from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn

from routers import files, database, analytics, templates

app = FastAPI(
    title="WC Optimizer API",
    description="Working Capital & Inventory Optimization API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(database.router, prefix="/api/database", tags=["database"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "wc-optimizer-api"}

@app.get("/")
def root():
    return {
        "message": "WC Optimizer API",
        "docs": "/docs",
        "endpoints": {
            "files": "/api/files",
            "database": "/api/database",
            "analytics": "/api/analytics",
            "templates": "/api/templates"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
