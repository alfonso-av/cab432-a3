from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
import os
from auth import get_current_user  # cognito

router = APIRouter(tags=["pages"])

directory_path = os.path.join(os.path.dirname(__file__), 'public')

@router.get("/")
async def main_page(user=Depends(get_current_user)):
    return FileResponse(os.path.join(directory_path, "index.html"))

@router.get("/admin")
async def admin_page(user=Depends(get_current_user)):
    # Replace old "users" dict check with Cognito claim
    if not user.get("custom:isAdmin", False):  # can add this as a custom attribute in Cognito
        raise HTTPException(status_code=403, detail="Unauthorised user requested admin content.")
    return FileResponse(os.path.join(directory_path, "admin.html"))
