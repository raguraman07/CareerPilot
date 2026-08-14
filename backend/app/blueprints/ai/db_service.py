import time
import logging
import uuid
from supabase_client import supabase_admin
from resume_routes import handle_supabase_op

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
        res = supabase_admin.table("resume_analyses") \
            .select("*") \
            .eq("resume_id", resume_id) \
            .eq("user_id", user_id) \
            .eq("status", "completed") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        return res.data[0] if res.data else None

    def mock_select():
        for item in MOCK_ANALYSES_DB.values():
            if item["resume_id"] == resume_id and item["user_id"] == user_id and item["status"] == "completed":
                logger.info(f"Database Service (Mock): Found cached analysis for resume_id {resume_id}")
                return item
        return None

    try:
        return handle_supabase_op(db_select, mock_select)
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
    Saves the resume analysis into the database using the atomic save_resume_analysis RPC.
    Also updates the parent resume's status to 'analyzed'.
    Returns the saved record dictionary or ID.
    """
    analysis_id = str(uuid.uuid4())
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def db_insert():
        logger.info(f"Database Service: Inserting analysis results for resume_id {resume_id}")
        try:
            # Call the public RPC function save_resume_analysis
            res = supabase_admin.rpc("save_resume_analysis", {
                "p_resume_id": resume_id,
                "p_user_id": user_id,
                "p_status": "completed",
                "p_analysis_results": analysis_results
            }).execute()
            
            return {
                "id": res.data if isinstance(res.data, str) else analysis_id,
                "resume_id": resume_id,
                "user_id": user_id,
                "status": "completed",
                "analysis_results": analysis_results,
                "created_at": created_at
            }
        except Exception as e:
            err_msg = str(e).lower()
            if "pgrst202" in err_msg or "function" in err_msg:
                logger.warning(f"RPC save_resume_analysis not found in database schema. Falling back to direct table updates: {e}")
                # Insert into public.resume_analyses
                ins_res = supabase_admin.table("resume_analyses").insert({
                    "id": analysis_id,
                    "resume_id": resume_id,
                    "user_id": user_id,
                    "status": "completed",
                    "analysis_results": analysis_results
                }).execute()
                # Update parent resume status to 'analyzed'
                supabase_admin.table("resumes").update({
                    "status": "analyzed"
                }).eq("id", resume_id).eq("user_id", user_id).execute()

                rec = ins_res.data[0] if ins_res.data else {
                    "id": analysis_id,
                    "resume_id": resume_id,
                    "user_id": user_id,
                    "status": "completed",
                    "analysis_results": analysis_results,
                    "created_at": created_at
                }
                return rec
            else:
                raise e

    def mock_insert():
        logger.info(f"Database Service (Mock): Inserting analysis record into in-memory DB")
        rec = {
            "id": analysis_id,
            "resume_id": resume_id,
            "user_id": user_id,
            "status": "completed",
            "analysis_results": analysis_results,
            "created_at": created_at
        }
        MOCK_ANALYSES_DB[analysis_id] = rec
        
        # Mock update the parent resume status in MOCK_RESUMES_DB
        try:
            from resume_routes import MOCK_RESUMES_DB
            if resume_id in MOCK_RESUMES_DB:
                MOCK_RESUMES_DB[resume_id]["status"] = "analyzed"
        except ImportError:
            pass
            
        return rec

    try:
        saved_rec = handle_supabase_op(db_insert, mock_insert)
        logger.info(f"Database Service: Successfully saved analysis with ID {analysis_id}")
        return saved_rec
    except Exception as e:
        logger.error(f"Database Service: Failed to save analysis results: {e}")
        raise e

def get_user_analysis_history(user_id):
    """
    Returns all previous analyses for the logged-in user, sorted by creation date descending.
    Includes the parent resume filename by performing a database join.
    """
    def db_select():
        logger.info(f"Database Service: Fetching analysis history for user_id {user_id}")
        # Joins resumes table to fetch the filename of the analyzed resume
        res = supabase_admin.table("resume_analyses") \
            .select("id, resume_id, status, analysis_results, created_at, resumes(filename)") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()
        return res.data

    def mock_select():
        user_list = []
        # Fallback to importing MOCK_RESUMES_DB to fetch filename
        mock_resumes = {}
        try:
            from resume_routes import MOCK_RESUMES_DB as mr_db
            mock_resumes = mr_db
        except ImportError:
            pass
            
        for item in MOCK_ANALYSES_DB.values():
            if item["user_id"] == user_id:
                # Find matching resume filename
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
        return handle_supabase_op(db_select, mock_select)
    except Exception as e:
        logger.error(f"Database Service: Failed to retrieve user analysis history: {e}")
        raise e
