import boto3
import os
import hmac
import hashlib
import base64
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from pydantic import BaseModel
import requests
import pyqrcode
import io
import base64 as b64

router = APIRouter(tags=["auth"])

# ---------------- AWS CONFIG ----------------
ssm = boto3.client("ssm", region_name="ap-southeast-2")
secrets = boto3.client("secretsmanager", region_name="ap-southeast-2")

def get_param(name: str) -> str:
    try:
        resp = ssm.get_parameter(Name=name)
        value = resp["Parameter"]["Value"]
        print(f"[Parameter Store] Loaded {name}: {value}")
        return value
    except Exception as e:
        print(f"[Parameter Store] Failed to load {name}: {e}")
        return None

REGION = get_param("/n10893997/aws_region")
USER_POOL_ID = get_param("/n10893997/cognito_user_pool_id")
CLIENT_ID = get_param("/n10893997/cognito_client_id")

# CLIENT_SECRET from Secrets Manager or fallback .env
try:
    secret_name = "/n10893997/cognito_client_secret"
    secret_resp = secrets.get_secret_value(SecretId=secret_name)
    CLIENT_SECRET = secret_resp["SecretString"]
    print(f"[Secrets Manager] Loaded {secret_name}")
except Exception as e:
    print(f"[Secrets Manager] Failed to load secret: {e}")
    CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET")

print(f"[DEBUG] REGION={REGION}")
print(f"[DEBUG] USER_POOL_ID={USER_POOL_ID}")
print(f"[DEBUG] CLIENT_ID={CLIENT_ID}")
print(f"[DEBUG] CLIENT_SECRET loaded? {'YES' if CLIENT_SECRET else 'NO'}")

cognito_client = boto3.client("cognito-idp", region_name=REGION)

# ---------------- Pydantic Schemas ----------------
class SignupRequest(BaseModel):
    username: str
    email: str
    password: str

class ConfirmRequest(BaseModel):
    username: str
    code: str

class LoginRequest(BaseModel):
    username: str
    password: str

class NewPasswordRequest(BaseModel):
    username: str
    new_password: str
    session: str

class RespondMFARequest(BaseModel):
    username: str
    code: str
    session: str

class SetupMFARequest(BaseModel):
    access_token: str

class VerifyMFARequest(BaseModel):
    access_token: str
    code: str

# ---------------- Helpers ----------------
def get_secret_hash(username: str) -> str:
    if not CLIENT_SECRET:
        return None
    message = username + CLIENT_ID
    dig = hmac.new(
        CLIENT_SECRET.encode("utf-8"),
        msg=message.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(dig).decode()

def is_admin(user: dict) -> bool:
    """Check if user belongs to Admin group in Cognito."""
    #print("[DEBUG] Decoded user payload:", user)
    groups = user.get("cognito:groups", [])
    if isinstance(groups, str):
        groups = [groups]
    is_admin_user = "Admin" in groups
    print(f"[DEBUG] is_admin={is_admin_user}, groups={groups}")
    return is_admin_user

# ---------------- ENDPOINTS ----------------
@router.post("/signup")
def signup(req: SignupRequest):
    try:
        kwargs = {
            "ClientId": CLIENT_ID,
            "Username": req.username,
            "Password": req.password,
            "UserAttributes": [{"Name": "email", "Value": req.email}],
        }
        if CLIENT_SECRET:
            kwargs["SecretHash"] = get_secret_hash(req.username)
        cognito_client.sign_up(**kwargs)
        return {"message": "User signup successful"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/confirm")
def confirm(req: ConfirmRequest):
    try:
        kwargs = {"ClientId": CLIENT_ID, "Username": req.username, "ConfirmationCode": req.code}
        if CLIENT_SECRET:
            kwargs["SecretHash"] = get_secret_hash(req.username)
        cognito_client.confirm_sign_up(**kwargs)
        return {"message": "User confirmed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
def login(req: LoginRequest):
    try:
        auth_params = {"USERNAME": req.username, "PASSWORD": req.password}
        if CLIENT_SECRET:
            auth_params["SECRET_HASH"] = get_secret_hash(req.username)

        resp = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters=auth_params,
        )

        if "ChallengeName" in resp:
            if resp["ChallengeName"] == "NEW_PASSWORD_REQUIRED":
                return {"challenge": "NEW_PASSWORD_REQUIRED", "session": resp["Session"]}
            elif resp["ChallengeName"] == "SOFTWARE_TOKEN_MFA":
                return {"challenge": "SOFTWARE_TOKEN_MFA", "session": resp["Session"]}

        auth_result = resp["AuthenticationResult"]

        # --- DEBUG LOGS ---
        print("\n--- LOGIN SUCCESS ---")
        print("ID Token (JWT):", auth_result["IdToken"][:80] + "...")
        print("Access Token:", auth_result["AccessToken"][:80] + "...")
        if "RefreshToken" in auth_result:
            print("Refresh Token:", auth_result["RefreshToken"][:80] + "...")
        print("---------------------\n")

        return {
            "id_token": auth_result["IdToken"],
            "access_token": auth_result["AccessToken"],
            "refresh_token": auth_result.get("RefreshToken"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cognito login error: {str(e)}")

@router.post("/complete-new-password")
def complete_new_password(req: NewPasswordRequest):
    try:
        challenge_responses = {
            "USERNAME": req.username,
            "NEW_PASSWORD": req.new_password,
        }
        if CLIENT_SECRET:
            challenge_responses["SECRET_HASH"] = get_secret_hash(req.username)

        resp = cognito_client.respond_to_auth_challenge(
            ClientId=CLIENT_ID,
            ChallengeName="NEW_PASSWORD_REQUIRED",
            Session=req.session,
            ChallengeResponses=challenge_responses,
        )

        auth_result = resp["AuthenticationResult"]

        # --- DEBUG LOGS ---
        print("\n--- LOGIN SUCCESS (NEW PASSWORD) ---")
        print("ID Token (JWT):", auth_result["IdToken"][:80] + "...")
        print("Access Token:", auth_result["AccessToken"][:80] + "...")
        if "RefreshToken" in auth_result:
            print("Refresh Token:", auth_result["RefreshToken"][:80] + "...")
        print("-----------------------------------\n")

        return {
            "id_token": auth_result["IdToken"],
            "access_token": auth_result["AccessToken"],
            "refresh_token": auth_result.get("RefreshToken"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cognito password update error: {str(e)}")

@router.post("/respond-mfa")
def respond_mfa(req: RespondMFARequest):
    try:
        challenge_responses = {
            "USERNAME": req.username,
            "SOFTWARE_TOKEN_MFA_CODE": req.code,
        }
        if CLIENT_SECRET:
            challenge_responses["SECRET_HASH"] = get_secret_hash(req.username)

        resp = cognito_client.respond_to_auth_challenge(
            ClientId=CLIENT_ID,
            ChallengeName="SOFTWARE_TOKEN_MFA",
            Session=req.session,
            ChallengeResponses=challenge_responses,
        )

        auth_result = resp["AuthenticationResult"]

        # --- DEBUG LOGS ---
        print("\n--- LOGIN SUCCESS (MFA) ---")
        print("ID Token (JWT):", auth_result["IdToken"][:80] + "...")
        print("Access Token:", auth_result["AccessToken"][:80] + "...")
        if "RefreshToken" in auth_result:
            print("Refresh Token:", auth_result["RefreshToken"][:80] + "...")
        print("---------------------------\n")

        return {
            "id_token": auth_result["IdToken"],
            "access_token": auth_result["AccessToken"],
            "refresh_token": auth_result.get("RefreshToken"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cognito MFA error: {str(e)}")

# ---------------- MFA SETUP ENDPOINTS ----------------
@router.post("/setup-mfa")
def setup_mfa(req: SetupMFARequest):
    try:
        resp = cognito_client.associate_software_token(
            AccessToken=req.access_token
        )
        secret = resp["SecretCode"]

        # Generate QR Code (PNG)
        uri = f"otpauth://totp/CAB432App?secret={secret}&issuer=CAB432App"
        qr = pyqrcode.create(uri)
        buffer = io.BytesIO()
        qr.png(buffer, scale=5)
        qr_b64 = b64.b64encode(buffer.getvalue()).decode("utf-8")

        return {"secret": secret, "qr_code": f"data:image/png;base64,{qr_b64}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Setup MFA failed: {str(e)}")

@router.post("/verify-mfa")
def verify_mfa(req: VerifyMFARequest):
    try:
        cognito_client.verify_software_token(
            AccessToken=req.access_token,
            UserCode=req.code,
            FriendlyDeviceName="MyAuthenticatorApp"
        )

        cognito_client.set_user_mfa_preference(
            SoftwareTokenMfaSettings={
                "Enabled": True,
                "PreferredMfa": True
            },
            AccessToken=req.access_token
        )

        return {"message": "MFA setup verified and enabled"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verify MFA failed: {str(e)}")

# ---------------- TOKEN VERIFICATION ----------------
bearer_scheme = HTTPBearer()
JWKS_URL = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
JWKS = requests.get(JWKS_URL).json()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    try:
        decoded = jwt.decode(
            token,
            JWKS,
            algorithms=["RS256"],
            audience=CLIENT_ID,
        )
        return decoded
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
