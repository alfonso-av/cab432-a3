from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import router as auth_router
from files import router as files_router
from jobs import router as jobs_router
from metadata import router as metadata_router

app = FastAPI(title="CAB432 A2 Video Transcoder")

# Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/auth")
app.include_router(files_router)
app.include_router(jobs_router)
app.include_router(metadata_router)

@app.get("/")
def root():
    return {"message": "CAB432 A2 API running"}
