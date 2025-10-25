Assignment 2 - Cloud Services Exercises - Response to Criteria
================================================

Instructions
------------------------------------------------
- Keep this file named A2_response_to_criteria.md, do not change the name
- Upload this file along with your code in the root directory of your project
- Upload this file in the current Markdown format (.md extension)
- Do not delete or rearrange sections.  If you did not attempt a criterion, leave it blank
- Text inside [ ] like [eg. S3 ] are examples and should be removed


Overview
------------------------------------------------

- **Name:** Alfonso Avenido
- **Student number:** n10893997
- **Partner name (if applicable):** 
- **Application name:** CAB432 A2 Video Transcoder
- **Two line description:** A video transcoding web application where users can upload, queue and download transcoded video files. Authentication and MFA are handled by Cognito, jobs and metadata by DynamoDB, and files by S3.
- **EC2 instance name or ID:** ec2-a2-05


------------------------------------------------

### Core - First data persistence service

- **AWS service name:** S3
- **What data is being stored?:** Original uploaded video files and transcoded outputs
- **Why is this service suited to this data?:** S3 is designed for storing large unstructured files (“blobs”) and supports secure direct uploads and downloads at scale.
- **Why is are the other services used not suitable for this data?:** DynamoDB is unsuitable for binary large objects, and EC2 instance storage is not persistent or scalable for this use case.
- **Bucket/instance/table name:** n10893997-videos
- **Video timestamp:** 2:04 min
- **Relevant files:**
    - files.py
    - frontend.py

### Core - Second data persistence service

- **AWS service name:** DynamoDB
- **What data is being stored?:** Metadata for uploaded and transcoded video jobs (filename, owner, status, S3 keys).
- **Why is this service suited to this data?:** DynamoDB provides fast key-value lookups, scales automatically, and allows easy mapping of jobs to users.
- **Why is are the other services used not suitable for this data?:** S3 is unsuitable for fast querying and filtering by job attributes; RDS would be unnecessarily complex for this workload.
- **Bucket/instance/table name:** n10893997-a2-jobs3
- **Video timestamp:** 2:04 min
- **Relevant files:**
    - files.py
    - jobs.py
    - frontend.py

### Third data service

- **AWS service name:** 
- **What data is being stored?:** 
- **Why is this service suited to this data?:**
- **Why is are the other services used not suitable for this data?:**
- **Bucket/instance/table name:**
- **Video timestamp:**
- **Relevant files:**
    -

### S3 Pre-signed URLs

- **S3 Bucket names:** n10893997-videos
- **Video timestamp:** 2:04 min and 2:46 min
- **Relevant files:**
    - files.py
    - frontend.py

### In-memory cache

- **ElastiCache instance name:**
- **What data is being cached?:**
- **Why is this data likely to be accessed frequently?:**
- **Video timestamp:**
- **Relevant files:**
    -

### Core - Statelessness

- **What data is stored within your application that is not stored in cloud data services?:** Only temporary in-memory dictionaries (FILES, JOBS) used for caching active state while the app is running.
- **Why is this data not considered persistent state?:** These dictionaries are recreated at startup by fetching from S3/DynamoDB, so no data is lost if the EC2 instance stops or restarts.
- **How does your application ensure data consistency if the app suddenly stops?:** All persistent state (uploaded files and job metadata) is already stored in S3 and DynamoDB; when the backend restarts it reloads state from these services, ensuring consistency.
- **Relevant files:**
    - files.py
    - jobs.py

### Graceful handling of persistent connections

- **Type of persistent connection and use:** 
- **Method for handling lost connections:** 
- **Relevant files:**
    -

### Core - Authentication with Cognito

- **User pool name:** n10893997-a2
- **How are authentication tokens handled by the client?:** After successful login, Cognito returns JWT tokens (ID, access, refresh). The frontend stores the ID and access tokens in session state and includes them in Authorization headers for subsequent requests.
- **Video timestamp:** 0:48 min
- **Relevant files:**
    - auth.py
    - frontend.py

### Cognito multi-factor authentication

- **What factors are used for authentication:** Password + TOTP (6-digit code via Google Authenticator)
- **Video timestamp:** 0:48 min
- **Relevant files:**
    - auth.py
    - frontend.py

### Cognito federated identities

- **Identity providers used:**
- **Video timestamp:**
- **Relevant files:**
    -

### Cognito groups

- **How are groups used to set permissions?:** Users in the Admin group can see, download and delete all users’ jobs. Normal users are restricted to their own uploads and jobs. The group claim is checked from the decoded Cognito JWT.
- **Video timestamp:** 2:57 min
- **Relevant files:**
    - auth.py
    - frontend.py

### Core - DNS with Route53

- **Subdomain**: n10893997.cab432.com
- **Video timestamp:** 0:00 min

### Parameter store

- **Parameter names:** 
  - /n10893997/aws_region  
  - /n10893997/cognito_client_id  
  - /n10893997/cognito_user_pool_id
- **Video timestamp:** 0:24 min
- **Relevant files:**
    - auth.py

### Secrets manager

- **Secrets names:** /n10893997/cognito_client_secret
- **Video timestamp:** 0:24 min
- **Relevant files:**
    - auth.py

### Infrastructure as code

- **Technology used:**
- **Services deployed:**
- **Video timestamp:**
- **Relevant files:**
    -

### Other (with prior approval only)

- **Description:**
- **Video timestamp:**
- **Relevant files:**
    -

### Other (with prior permission only)

- **Description:**
- **Video timestamp:**
- **Relevant files:**
    -

