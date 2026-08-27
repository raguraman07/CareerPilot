import os
import json
import logging
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, auth

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

FIREBASE_SERVICE_ACCOUNT_ENV = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()

db = None
firebase_auth = auth
is_firebase_configured = False

try:
    cred = None
    # 1. Check if environment variable contains raw JSON string
    if FIREBASE_SERVICE_ACCOUNT_ENV.startswith("{") and FIREBASE_SERVICE_ACCOUNT_ENV.endswith("}"):
        try:
            cert_dict = json.loads(FIREBASE_SERVICE_ACCOUNT_ENV)
            cred = credentials.Certificate(cert_dict)
            logger.info("Firebase Admin SDK initializing with JSON string from environment variable.")
        except Exception as json_err:
            logger.warning(f"Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON as JSON string: {json_err}")

    # 2. Check if environment variable specifies a valid file path
    if not cred and FIREBASE_SERVICE_ACCOUNT_ENV:
        json_path = FIREBASE_SERVICE_ACCOUNT_ENV
        if not os.path.isabs(json_path):
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(backend_dir, json_path)
        if os.path.exists(json_path):
            cred = credentials.Certificate(json_path)
            logger.info(f"Firebase Admin SDK initializing with file path: {json_path}")

    # 3. Default fallback to local firebase/serviceAccountKey.json
    if not cred:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(backend_dir, "firebase", "serviceAccountKey.json")
        if os.path.exists(default_path):
            cred = credentials.Certificate(default_path)
            logger.info(f"Firebase Admin SDK initializing with default path: {default_path}")

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

