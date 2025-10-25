#!/bin/bash
# load_test.sh

set -e

# 1. Get token
TOKEN=$(curl -s -X POST http://localhost:3000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"CAB432","password":"supersecret"}' | jq -r .authToken)

# 2. Upload test file once
FILE_ID=$(curl -s -X POST "http://localhost:3000/files" \
  -H "Authorization: Bearer $TOKEN" \
  -F "uploaded=@sample_input.mp4" | jq -r .file_id)

echo "Uploaded sample_input.mp4 with file_id=$FILE_ID"

# 3. Launch a set number of parallel jobs 
NUM_JOBS=32
for i in $(seq 1 $NUM_JOBS); do
  curl -s -X POST "http://localhost:3000/jobs/parallel?file_id=$FILE_ID" \
    -H "Authorization: Bearer $TOKEN" > /dev/null &
done

echo "Launched $NUM_JOBS parallel jobs. check htop"
wait
