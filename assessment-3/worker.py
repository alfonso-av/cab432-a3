import boto3, json, time, os, subprocess, traceback
from datetime import datetime

# THIS IS THE WORKER PYTHON FILE
# JUST ADDED HERE FOR THE SUBMISSION

# ---------------- CONFIG ----------------
REGION = "ap-southeast-2"
SQS_QUEUE_URL = "https://sqs.ap-southeast-2.amazonaws.com/901444280953/n10893997-sqs-a3"
S3_BUCKET = "n10893997-videos"
JOBS_TABLE = "n10893997-a2-jobs3"

# ---------------- CLIENTS ----------------
sqs = boto3.client("sqs", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.client("dynamodb", region_name=REGION)

# ---------------- FFMPEG RUNNER ----------------
def run_ffmpeg(input_path, output_path):
    """Runs a multi-pass FFmpeg process to simulate heavy CPU load."""
    for i in range(3):  # Run 3 passes for consistent load during demo
        temp_output = f"/tmp/loop_{i}.mp4"
        print(f"[WORKER] Pass {i+1}/3 - running FFmpeg on {input_path} → {temp_output}")

        subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            "-vf", "scale=1920:1080,eq=contrast=1.8:brightness=0.08:saturation=1.8,unsharp=5:5:1.0",
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-threads", "0",
            "-c:a", "aac",
            "-b:a", "256k",
            temp_output
        ], check=True)

        input_path = temp_output

    os.rename(temp_output, output_path)


# ---------------- MAIN WORKER LOOP ----------------
while True:
    try:
        # Poll SQS queue for messages
        resp = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
        )

        messages = resp.get("Messages", [])
        if not messages:
            # No messages found, wait before polling again
            time.sleep(2)
            continue

        for msg in messages:
            try:
                body = json.loads(msg["Body"])
                print("------------------------------------------------------------")
                print("[DEBUG] Received message:", json.dumps(body, indent=2))

                # Extract relevant fields from the message
                user = body.get("username") or body.get("cognito:username")
                job_id = body.get("jobs_id")
                s3_key = body.get("s3_key")

                if not all([user, job_id, s3_key]):
                    raise ValueError(f"Incomplete message data: {body}")

                print(f"[WORKER] Processing job {job_id} for user {user}")

                # Step 1: Update DynamoDB to mark job as 'processing'
                dynamodb.update_item(
                    TableName=JOBS_TABLE,
                    Key={"qut-username": {"S": user}, "jobs_id": {"S": job_id}},
                    UpdateExpression="SET #s=:s, started=:t",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":s": {"S": "processing"},
                        ":t": {"S": datetime.utcnow().isoformat()},
                    },
                )

                # Step 2: Download the input video from S3
                filename = os.path.basename(s3_key)
                input_path = f"/tmp/{filename}"
                output_path = f"/tmp/transcoded_{filename}"
                s3.download_file(S3_BUCKET, s3_key, input_path)

                # Step 3: Run FFmpeg transcoding process
                run_ffmpeg(input_path, output_path)

                # Step 4: Upload the transcoded video back to S3
                output_s3_key = f"{user}/transcoded_{filename}"
                s3.upload_file(output_path, S3_BUCKET, output_s3_key)

                # Step 5: Update DynamoDB to mark job as 'completed'
                dynamodb.update_item(
                    TableName=JOBS_TABLE,
                    Key={"qut-username": {"S": user}, "jobs_id": {"S": job_id}},
                    UpdateExpression="SET #s=:s, finished=:f",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":s": {"S": "completed"},
                        ":f": {"S": datetime.utcnow().isoformat()},
                    },
                )

                # Step 6: Remove message from SQS to prevent reprocessing
                sqs.delete_message(
                    QueueUrl=SQS_QUEUE_URL,
                    ReceiptHandle=msg["ReceiptHandle"]
                )

                print(f"[WORKER] Job {job_id} completed successfully for {user}")

            except Exception as e:
                print(f"[WORKER] Error processing message: {e}")
                traceback.print_exc()

                # Delete message to prevent stuck or looping messages
                sqs.delete_message(
                    QueueUrl=SQS_QUEUE_URL,
                    ReceiptHandle=msg["ReceiptHandle"]
                )
                print("[WORKER] Removed malformed or failed message from queue")

    except KeyboardInterrupt:
        print("Worker stopped manually.")
        break
    except Exception as e:
        # Catch global errors to keep the worker running
        print(f"[WORKER] Global error: {e}")
        time.sleep(5)
