import os, uuid, asyncio, subprocess, boto3
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user, is_admin

router = APIRouter(tags=["jobs"])

# ---------------- AWS CONFIG ----------------
REGION = "ap-southeast-2"
JOBS_TABLE = "n10893997-a2-jobs3"
S3_BUCKET = "n10893997-videos"
SQS_QUEUE_URL = "https://sqs.ap-southeast-2.amazonaws.com/901444280953/n10893997-sqs-a3"

dynamodb = boto3.client("dynamodb", region_name=REGION)
# s3_client = boto3.client("s3", region_name=REGION)
sqs = boto3.client("sqs", region_name=REGION)


# ---------------- JOB RUNNER ----------------
async def run_job(jobs_id: str, username: str, s3_key: str):
    """Transcode a video job with ffmpeg and update DynamoDB"""
    original_name = os.path.basename(s3_key)
    name_no_ext, ext = os.path.splitext(original_name)

    output_filename = f"{name_no_ext}_transcoded{ext}"
    output_path = os.path.join("data", "output", output_filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        # Mark job as processing
        dynamodb.update_item(
            TableName=JOBS_TABLE,
            Key={"qut-username": {"S": username}, "jobs_id": {"S": jobs_id}},
            UpdateExpression="SET #st = :s, started = :t",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":s": {"S": "processing"},
                ":t": {"S": datetime.utcnow().isoformat()},
            },
        )

        # Download input file from S3
        input_path = os.path.join("data", "input", original_name)
        os.makedirs(os.path.dirname(input_path), exist_ok=True)
        s3_client.download_file(S3_BUCKET, s3_key, input_path)

        # Run ffmpeg asynchronously (use all CPU threads to trigger autoscaling faster)
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", "libx264",
            "-preset", "medium",   # "medium" or "slow" = higher CPU usage
            "-threads", "0",       # use all available cores
            output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )


        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=300)
            print(stdout.decode())  # ffmpeg logs
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise Exception("Transcoding timed out")

        if process.returncode != 0:
            raise Exception(f"FFmpeg failed with code {process.returncode}")

        # Upload transcoded file to S3
        output_s3_key = f"{username}/{output_filename}"
        s3_client.upload_file(output_path, S3_BUCKET, output_s3_key)

        # Mark job as completed
        dynamodb.update_item(
            TableName=JOBS_TABLE,
            Key={"qut-username": {"S": username}, "jobs_id": {"S": jobs_id}},
            UpdateExpression="SET #st = :s, #out = :o, finished = :f",
            ExpressionAttributeNames={
                "#st": "status",
                "#out": "output",
            },
            ExpressionAttributeValues={
                ":s": {"S": "completed"},
                ":o": {"S": output_s3_key},
                ":f": {"S": datetime.utcnow().isoformat()},
            },
        )

    except Exception as e:
        # Mark job as failed
        dynamodb.update_item(
            TableName=JOBS_TABLE,
            Key={"qut-username": {"S": username}, "jobs_id": {"S": jobs_id}},
            UpdateExpression="SET #st = :s, #err = :e, finished = :f",
            ExpressionAttributeNames={
                "#st": "status",
                "#err": "error",
            },
            ExpressionAttributeValues={
                ":s": {"S": "failed"},
                ":e": {"S": str(e)},
                ":f": {"S": datetime.utcnow().isoformat()},
            },
        )


# ---------------- START JOBS ----------------
@router.post("/jobs/start")
async def start_jobs(user=Depends(get_current_user)):
    """Queue all 'queued' jobs into SQS for the worker to process."""
    try:
        resp = dynamodb.query(
            TableName=JOBS_TABLE,
            KeyConditionExpression="#u = :u",
            ExpressionAttributeNames={"#u": "qut-username"},
            ExpressionAttributeValues={":u": {"S": user["cognito:username"]}},
        )
        items = resp.get("Items", [])
        sent = 0

        for item in items:
            status = item.get("status", {}).get("S", "")
            if status == "queued":
                jobs_id = item["jobs_id"]["S"]
                s3_key = item["s3_key"]["S"]

                msg = {
                    "username": user["cognito:username"],
                    "jobs_id": jobs_id,
                    "s3_key": s3_key,
                }

                sqs.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(msg))

                # Optional: update DynamoDB status
                dynamodb.update_item(
                    TableName=JOBS_TABLE,
                    Key={"qut-username": {"S": user["cognito:username"]}, "jobs_id": {"S": jobs_id}},
                    UpdateExpression="SET #s = :s, queued_at = :t",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":s": {"S": "queued"},
                        ":t": {"S": datetime.utcnow().isoformat()},
                    },
                )
                sent += 1

        return {"message": f"{sent} jobs sent to SQS for processing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# @router.post("/jobs/start")
# async def start_jobs(user=Depends(get_current_user)):
#     """Start transcoding all queued jobs for the current user"""
#     try:
#         resp = dynamodb.query(
#             TableName=JOBS_TABLE,
#             KeyConditionExpression="#u = :u",
#             ExpressionAttributeNames={"#u": "qut-username"},
#             ExpressionAttributeValues={":u": {"S": user["cognito:username"]}},
#         )
#         items = resp.get("Items", [])
#         started = []

#         for item in items:
#             status = item.get("status", {}).get("S", "")
#             if status == "queued":
#                 jobs_id = item["jobs_id"]["S"]
#                 s3_key = item["s3_key"]["S"]

#                 # Launch transcoding asynchronously
#                 asyncio.create_task(run_job(jobs_id, user["cognito:username"], s3_key))
#                 started.append(jobs_id)

#         return {"message": f"Started {len(started)} jobs", "jobs": started}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# ---------------- LIST JOBS ----------------
@router.get("/jobs")
async def list_jobs(user=Depends(get_current_user)):
    """List jobs. Admins see all, users see only their own"""
    try:
        if is_admin(user):
            print(f"[DEBUG] {user['cognito:username']} is ADMIN → scan")
            resp = dynamodb.scan(TableName=JOBS_TABLE)
        else:
            print(f"[DEBUG] {user['cognito:username']} is NORMAL USER → query")
            resp = dynamodb.query(
                TableName=JOBS_TABLE,
                KeyConditionExpression="#u = :u",
                ExpressionAttributeNames={"#u": "qut-username"},
                ExpressionAttributeValues={":u": {"S": user["cognito:username"]}},
            )

        jobs = [{k: list(v.values())[0] for k, v in item.items()} for item in resp.get("Items", [])]
        return {"jobs": jobs}
    except Exception as e:
        print("[ERROR] /jobs failed:", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- DELETE JOB ----------------
@router.delete("/jobs/{jobs_id}")
def delete_job(jobs_id: str, user=Depends(get_current_user)):
    """Delete a job. Admins can delete any, users only their own"""
    try:
        if is_admin(user):
            # Admin: find owner first
            resp = dynamodb.scan(
                TableName=JOBS_TABLE,
                FilterExpression="jobs_id = :j",
                ExpressionAttributeValues={":j": {"S": jobs_id}},
            )
            items = resp.get("Items", [])
            if not items:
                raise HTTPException(status_code=404, detail="Job not found")
            job = items[0]
            owner = job["qut-username"]["S"]

            # Delete from DynamoDB
            dynamodb.delete_item(
                TableName=JOBS_TABLE,
                Key={"qut-username": {"S": owner}, "jobs_id": {"S": jobs_id}},
            )

            # Delete files from S3 if present
            if "s3_key" in job:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=job["s3_key"]["S"])
            if "output" in job:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=job["output"]["S"])

            print(f"[DEBUG] Admin {user['cognito:username']} deleted job {jobs_id}")
            return {"message": f"Admin deleted job {jobs_id} successfully"}

        else:
            # Normal user: only delete their own job
            resp = dynamodb.get_item(
                TableName=JOBS_TABLE,
                Key={
                    "qut-username": {"S": user["cognito:username"]},
                    "jobs_id": {"S": jobs_id},
                },
            )
            if "Item" not in resp:
                raise HTTPException(status_code=403, detail="You cannot delete jobs that aren't yours")

            job = resp["Item"]

            # Delete from DynamoDB
            dynamodb.delete_item(
                TableName=JOBS_TABLE,
                Key={
                    "qut-username": {"S": user["cognito:username"]},
                    "jobs_id": {"S": jobs_id},
                },
            )

            # Delete files from S3 if present
            if "s3_key" in job:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=job["s3_key"]["S"])
            if "output" in job:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=job["output"]["S"])

            print(f"[DEBUG] User {user['cognito:username']} deleted job {jobs_id}")
            return {"message": f"Job {jobs_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
