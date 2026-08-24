import os
import logging
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, auth

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", r"firebase\serviceAccountKey.json")

# Ensure absolute path resolution if relative
if not os.path.isabs(FIREBASE_SERVICE_ACCOUNT_JSON):
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    FIREBASE_SERVICE_ACCOUNT_JSON = os.path.join(backend_dir, FIREBASE_SERVICE_ACCOUNT_JSON)

db = None
firebase_auth = auth

is_firebase_configured = False

try:
    if os.path.exists(FIREBASE_SERVICE_ACCOUNT_JSON):
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_JSON)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        is_firebase_configured = True
        logger.info(f"Firebase Admin SDK initialized successfully with credentials: {FIREBASE_SERVICE_ACCOUNT_JSON}")
    else:
        logger.warning(f"Firebase service account file not found at: {FIREBASE_SERVICE_ACCOUNT_JSON}")
except Exception as err:
    logger.error(f"Failed to initialize Firebase Admin SDK: {err}")
