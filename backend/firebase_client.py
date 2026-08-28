import os
import json
import base64
import logging
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, auth

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

db = None
firebase_auth = auth
is_firebase_configured = False

def _build_credentials():
    """
    Attempts to construct Firebase Admin credentials using flexible configuration:
    1. Full JSON string in FIREBASE_SERVICE_ACCOUNT_JSON (or base64 encoded)
    2. Individual environment variables (FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, FIREBASE_PRIVATE_KEY)
    3. GOOGLE_APPLICATION_CREDENTIALS / file path in FIREBASE_SERVICE_ACCOUNT_JSON
    4. Local development default file: backend/firebase/serviceAccountKey.json
    """
    # 1. Check FIREBASE_SERVICE_ACCOUNT_JSON / FIREBASE_CREDENTIALS_JSON
    raw_json_env = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or os.getenv("FIREBASE_CREDENTIALS_JSON") or ""
    raw_json_env = raw_json_env.strip()
    
    if raw_json_env:
        # Check if base64 encoded
        if not raw_json_env.startswith("{") and not os.path.exists(raw_json_env):
            try:
                decoded = base64.b64decode(raw_json_env).decode("utf-8")
                if decoded.strip().startswith("{"):
                    raw_json_env = decoded.strip()
            except Exception:
                pass

        # Try parsing JSON string
        if raw_json_env.startswith("{") and raw_json_env.endswith("}"):
            try:
                cert_dict = json.loads(raw_json_env)
                # Handle unescaped \n in private_key if needed
                if "private_key" in cert_dict and isinstance(cert_dict["private_key"], str):
                    cert_dict["private_key"] = cert_dict["private_key"].replace("\\n", "\n")
                logger.info("Firebase Admin SDK initializing with JSON string from environment variable.")
                return credentials.Certificate(cert_dict)
            except Exception as json_err:
                logger.warning(f"Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON as JSON string: {json_err}")
        else:
            # Check if it specifies a valid file path
            json_path = raw_json_env
            if not os.path.isabs(json_path):
                backend_dir = os.path.dirname(os.path.abspath(__file__))
                json_path = os.path.join(backend_dir, json_path)
            if os.path.exists(json_path):
                logger.info(f"Firebase Admin SDK initializing with file path: {json_path}")
                return credentials.Certificate(json_path)

    # 2. Check individual environment variables (Render standard friendly pattern)
    project_id = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GCP_PROJECT_ID")
    client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
    private_key = os.getenv("FIREBASE_PRIVATE_KEY")

    if project_id and client_email and private_key:
        try:
            # Normalize private key newlines
            clean_private_key = private_key.replace("\\n", "\n").strip()
            # If wrapped with surrounding quotes in env var, strip them
            if (clean_private_key.startswith('"') and clean_private_key.endswith('"')) or (clean_private_key.startswith("'") and clean_private_key.endswith("'")):
                clean_private_key = clean_private_key[1:-1].replace("\\n", "\n").strip()

            cert_dict = {
                "type": "service_account",
                "project_id": project_id.strip(),
                "private_key": clean_private_key,
                "client_email": client_email.strip(),
                "token_uri": "https://oauth2.googleapis.com/token"
            }
            logger.info("Firebase Admin SDK initializing with individual environment variables.")
            return credentials.Certificate(cert_dict)
        except Exception as ind_err:
            logger.warning(f"Failed to initialize Firebase with individual environment variables: {ind_err}")

    # 3. Check GOOGLE_APPLICATION_CREDENTIALS
    gac_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if gac_path and os.path.exists(gac_path):
        logger.info(f"Firebase Admin SDK initializing via GOOGLE_APPLICATION_CREDENTIALS: {gac_path}")
        return credentials.Certificate(gac_path)

    # 4. Default fallback for local development: backend/firebase/serviceAccountKey.json
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    default_path = os.path.join(backend_dir, "firebase", "serviceAccountKey.json")
    if os.path.exists(default_path):
        logger.info(f"Firebase Admin SDK initializing with local default path: {default_path}")
        return credentials.Certificate(default_path)

    return None

try:
    cred = _build_credentials()
    if cred:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        is_firebase_configured = True
        logger.info("Firebase Admin SDK initialized successfully.")
    else:
        logger.warning("Firebase service account credentials not configured.")
except Exception as err:
    logger.error(f"Failed to initialize Firebase Admin SDK: {err}")
