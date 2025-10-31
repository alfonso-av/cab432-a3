import boto3, json, time, os, subprocess, traceback
from datetime import datetime

# ---------------- CONFIG ----------------
REGION = "ap-southeast-2"
SQS_QUEUE_URL = "https://sqs.ap-southeast-2.amazonaws.com/901444280953/n10893997-sqs-a3"
S3_BUCKET = "n10893997-videos"
JOBS_TABLE = "n10893997-a2-jobs3"

# ---------------- AWS CLIENTS ----------------
sqs = boto3.client("sqs", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.client("dynamodb", region_name=REGION)

# ---------------- FFMPEG RUNNER ----------------
def run_ffmpeg(input_path, output_path):
    # 3 passes to simulate heavy transcoding (for demo load)
    for i in range(3):
        temp_output = f"/tmp/loop_{i}.mp4"
        print(f"[WORKER] Pass {i+1}/3 - transcoding {input_path} → {temp_output}")

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
        # Poll SQS for new messages
        resp = sqs.receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
        )

        messages = resp.get("Messages", [])
        if not messages:
            time.sleep(2)
            continue

        for msg in messages:
            try:
                body = json.loads(msg["Body"])
                print("------------------------------------------------------------")
                print("[DEBUG] Received message:", json.dumps(body, indent=2))

                # Ignore random S3-trigger events
                if "bucket" in body and "action" in body:
                    print("[WORKER] Ignored S3-trigger message.")
                    sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
                    continue

                # Extract job info
                user = body.get("username") or body.get("cognito:username")
                job_id = body.get("jobs_id")
                s3_key = body.get("s3_key")

                if not all([user, job_id, s3_key]):
                    raise ValueError(f"Incomplete message data: {body}")

                print(f"[WORKER] Processing job {job_id} for {user}")

                # Mark job as 'processing'
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

                # Download source video
                filename = os.path.basename(s3_key)
                input_path = f"/tmp/{filename}"
                output_path = f"/tmp/transcoded_{filename}"
                s3.download_file(S3_BUCKET, s3_key, input_path)

                # Uncomment below to test DLQ behaviour
                # raise Exception("Simulated failure for DLQ test")

                # Run FFmpeg
                run_ffmpeg(input_path, output_path)

                # Upload finished video
                output_s3_key = f"{user}/transcoded_{filename}"
                s3.upload_file(output_path, S3_BUCKET, output_s3_key)

                # Mark as completed
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

                # Delete from queue once done
                sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
                print(f"[WORKER] ✅ Completed job {job_id} for {user}")

            except ValueError as e:
                # Skip bad messages
                print(f"[WORKER] Malformed message: {e}")
                sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])

            except Exception as e:
                # Let SQS handle retries / DLQ
                print(f"[WORKER] Error processing job: {e}")
                traceback.print_exc()
                print("[WORKER] Message left for retry or DLQ transfer.")

    except KeyboardInterrupt:
        print("Worker stopped manually.")
        break
    except Exception as e:
        # Catch any loop-level errors
        print(f"[WORKER] Global error: {e}")
        time.sleep(5)
