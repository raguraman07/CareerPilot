import time
import logging
import uuid
from firebase_client import db
from resume_routes import handle_db_op

logger = logging.getLogger(__name__)

# Local in-memory fallback database for local offline testing
MOCK_ANALYSES_DB = {}

def get_cached_analysis(resume_id, user_id):
    """
    Checks if a completed analysis already exists for this resume and user.
    If it exists, returns the full analysis dictionary record, otherwise returns None.
    """
    def db_select():
        logger.info(f"Database Service: Checking cache for resume_id {resume_id} and user_id {user_id}")
        docs = db.collection("resume_analyses").where("resume_id", "==", resume_id).where("user_id", "==", user_id).where("status", "==", "completed").stream()
        records = [d.to_dict() for d in docs]
        if records:
            sorted_records = sorted(records, key=lambda x: x.get("created_at", ""), reverse=True)
            return sorted_records[0]
        return None

    def mock_select():
        for item in MOCK_ANALYSES_DB.values():
            if item["resume_id"] == resume_id and item["user_id"] == user_id and item["status"] == "completed":
                logger.info(f"Database Service (Mock): Found cached analysis for resume_id {resume_id}")
                return item
        return None

    try:
        return handle_db_op(db_select, mock_select)
    except Exception as e:
        logger.error(f"Database Service: Error checking cached analysis: {e}")
        return None

def get_analysis_by_resume_id(resume_id, user_id):
    """
    Retrieves the existing analysis record for a given resume_id belonging to user_id.
    """
    return get_cached_analysis(resume_id, user_id)

def save_analysis(resume_id, user_id, analysis_results):
    """
    Saves the resume analysis into Firestore.
    Also updates the parent resume's status to 'analyzed'.
    Returns the saved record dictionary or ID.
    """
    analysis_id = str(uuid.uuid4())
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec = {
        "id": analysis_id,
        "resume_id": resume_id,
        "user_id": user_id,
        "status": "completed",
        "analysis_results": analysis_results,
        "created_at": created_at
    }

    def db_insert():
        logger.info(f"Database Service: Inserting analysis results for resume_id {resume_id}")
        db.collection("resume_analyses").document(analysis_id).set(rec)
        try:
            db.collection("resumes").document(resume_id).update({"status": "analyzed"})
        except Exception:
            pass
        return rec

    def mock_insert():
        logger.info(f"Database Service (Mock): Inserting analysis record into in-memory DB")
        MOCK_ANALYSES_DB[analysis_id] = rec
        try:
            from resume_routes import MOCK_RESUMES_DB
            if resume_id in MOCK_RESUMES_DB:
                MOCK_RESUMES_DB[resume_id]["status"] = "analyzed"
        except ImportError:
            pass
        return rec

    try:
        saved_rec = handle_db_op(db_insert, mock_insert)
        logger.info(f"Database Service: Successfully saved analysis with ID {analysis_id}")
        return saved_rec
    except Exception as e:
        logger.error(f"Database Service: Failed to save analysis results: {e}")
        raise e

def get_user_analysis_history(user_id):
    """
    Returns all previous analyses for the logged-in user, sorted by creation date descending.
    Includes the parent resume filename by performing a database lookup.
    """
    def db_select():
        logger.info(f"Database Service: Fetching analysis history for user_id {user_id}")
        docs = db.collection("resume_analyses").where("user_id", "==", user_id).stream()
        records = []
        for doc in docs:
            d = doc.to_dict()
            try:
                res_doc = db.collection("resumes").document(d.get("resume_id")).get()
                if res_doc.exists:
                    d["resumes"] = {"filename": res_doc.to_dict().get("filename")}
            except Exception:
                pass
            records.append(d)
        return sorted(records, key=lambda x: x.get("created_at", ""), reverse=True)

    def mock_select():
        user_list = []
        mock_resumes = {}
        try:
            from resume_routes import MOCK_RESUMES_DB as mr_db
            mock_resumes = mr_db
        except ImportError:
            pass
            
        for item in MOCK_ANALYSES_DB.values():
            if item["user_id"] == user_id:
                res_obj = mock_resumes.get(item["resume_id"])
                filename = res_obj["filename"] if res_obj else "unknown_resume.pdf"
                
                user_list.append({
                    "id": item["id"],
                    "resume_id": item["resume_id"],
                    "status": item["status"],
                    "analysis_results": item["analysis_results"],
                    "created_at": item["created_at"],
                    "resumes": {
                        "filename": filename
                    }
                })
        return sorted(user_list, key=lambda x: x["created_at"], reverse=True)

    try:
        return handle_db_op(db_select, mock_select)
    except Exception as e:
        logger.error(f"Database Service: Failed to retrieve user analysis history: {e}")
        raise e
