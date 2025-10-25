import os, uuid, boto3
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from typing import Optional
from auth import get_current_user

router = APIRouter(tags=["files"])

# ---------------- AWS CONFIG ----------------
REGION = "ap-southeast-2"
S3_BUCKET = "n10893997-videos"
UPLOADS_TABLE = "n10893997-a2"
JOBS_TABLE = "n10893997-a2-jobs3"

s3_client = boto3.client("s3", region_name=REGION)
dynamodb = boto3.client("dynamodb", region_name=REGION)

# ---------------- Presigned Upload ----------------
@router.post("/upload-url")
def get_upload_url(filename: str, user=Depends(get_current_user)):
    """Generate a presigned S3 URL for direct upload"""
    try:
        file_id = str(uuid.uuid4())
        s3_key = f"{user['cognito:username']}/{file_id}_{filename}"

        url = s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=3600,
        )

        return {"upload_url": url, "s3_key": s3_key, "file_id": file_id, "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm-upload")
def confirm_upload(file_id: str, s3_key: str, filename: str, imdbID: Optional[str] = "", user=Depends(get_current_user)):
    """Confirm upload, save metadata to DynamoDB, and queue a job"""
    try:
        username = user["cognito:username"]

        # Save upload metadata
        dynamodb.put_item(
            TableName=UPLOADS_TABLE,
            Item={
                "qut-username": {"S": username},
                "file_id": {"S": file_id},
                "filename": {"S": filename},
                "uploaded": {"S": datetime.utcnow().isoformat()},
                "imdbID": {"S": imdbID or ""},
                "s3_key": {"S": s3_key},
            },
        )

        # Create a queued job
        job_id = str(uuid.uuid4())
        dynamodb.put_item(
            TableName=JOBS_TABLE,
            Item={
                "qut-username": {"S": username},
                "jobs_id": {"S": job_id},
                "file_id": {"S": file_id},
                "filename": {"S": filename},
                "s3_key": {"S": s3_key},
                "status": {"S": "queued"},
                "created": {"S": datetime.utcnow().isoformat()},
            },
        )

        return {"message": "File metadata saved and job queued", "file_id": file_id, "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- Presigned Download ----------------
@router.get("/download-url/{file_id}")
def get_download_url(file_id: str, user=Depends(get_current_user)):
    """Generate a presigned S3 URL for original file download"""
    try:
        resp = dynamodb.get_item(
            TableName=UPLOADS_TABLE,
            Key={"qut-username": {"S": user["cognito:username"]}, "file_id": {"S": file_id}},
        )
        if "Item" not in resp:
            raise HTTPException(status_code=404, detail="File not found")

        s3_key = resp["Item"]["s3_key"]["S"]

        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=3600,
        )
        return {"download_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{jobs_id}")
def download_file(jobs_id: str, user=Depends(get_current_user)):
    """Generate a presigned S3 URL for transcoded file download"""
    try:
        resp = dynamodb.get_item(
            TableName=JOBS_TABLE,
            Key={"qut-username": {"S": user["cognito:username"]}, "jobs_id": {"S": jobs_id}},
        )
        if "Item" not in resp:
            raise HTTPException(status_code=404, detail="Job not found")

        item = resp["Item"]
        if item.get("status", {}).get("S") != "completed":
            raise HTTPException(status_code=400, detail="File not ready for download")

        s3_key = item["output"]["S"]

        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=3600,
        )
        print("[DEBUG] Pre-signed URL generated:", url)

        return {"download_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
