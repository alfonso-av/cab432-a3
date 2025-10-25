import boto3
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user

router = APIRouter(tags=["metadata"])

REGION = "ap-southeast-2"
UPLOADS_TABLE = "n10893997-a2"
dynamodb = boto3.client("dynamodb", region_name=REGION)

@router.get("/files/{file_id}/full_metadata")
def get_file_metadata(file_id: str, user=Depends(get_current_user)):
    try:
        resp = dynamodb.get_item(
            TableName=UPLOADS_TABLE,
            Key={"qut-username": {"S": user["cognito:username"]}, "file_id": {"S": file_id}},
        )
        if "Item" not in resp:
            raise HTTPException(status_code=404, detail="File not found")
        item = {k: list(v.values())[0] for k, v in resp["Item"].items()}
        return item
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
