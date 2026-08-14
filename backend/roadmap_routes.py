import os
import json
import logging
from flask import Blueprint, request, jsonify
from supabase_client import supabase_admin
from resume_routes import get_auth_uid, handle_supabase_op
import google.generativeai as genai

logger = logging.getLogger(__name__)

roadmap_bp = Blueprint('roadmap', __name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_mock = not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your-") or GEMINI_API_KEY.startswith("dummy")

if not is_gemini_mock:
    genai.configure(api_key=GEMINI_API_KEY)

# Mock fallback data for Career Roadmap
MOCK_ROADMAP_DATA = {
    "roadmap_json": {
        "milestones": [
            {
                "phase": "Phase 1: Foundation & Version Control",
                "duration": "1-2 weeks",
                "topics": ["Python Advanced Concepts", "Git and GitHub Branching Strategies"],
                "description": "Strengthen python core syntax, object-oriented concepts, and learn collaborative code practices using Git."
            },
            {
                "phase": "Phase 2: Relational Databases & Server APIs",
                "duration": "3-4 weeks",
                "topics": ["SQL Queries & Indices", "REST API standards with Flask", "Row-Level Security (RLS)"],
                "description": "Understand database designs, construct server endpoints, and learn how to secure public data APIs."
            },
            {
                "phase": "Phase 3: Deployment & Cloud",
                "duration": "2 weeks",
                "topics": ["Docker Containers", "Supabase DB Hosting", "CI/CD Actions"],
                "description": "Containerize your Flask backend app and deploy it on modern hosting platforms connected to Supabase."
            }
        ]
    }
}

# In-memory database fallback for local testing
MOCK_ROADMAP_DB = {}

@roadmap_bp.route('/api/roadmap/generate', methods=['POST'])
def generate_career_roadmap():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    goal = data.get("goal")
    current_level = data.get("current_level") or "Entry-Level"

    if not goal:
        return jsonify({"error": "Missing goal (target career role) in request."}), 400

    roadmap_result = None

    if is_gemini_mock:
        roadmap_result = MOCK_ROADMAP_DATA
    else:
        try:
            prompt = f"""
            You are an expert career growth planner and technical mentor.
            Generate a detailed chronological step-by-step career path roadmap to achieve the goal: '{goal}', starting from '{current_level}'.
            
            You must return a raw JSON object matching the exact structure below:
            {{
                "roadmap_json": {{
                    "milestones": [
                        {{
                            "phase": "Phase Name / Title",
                            "duration": "Estimated time (e.g. 2 weeks)",
                            "topics": ["topic1", "topic2"],
                            "description": "Short explanation of objectives"
                        }}
                    ]
                }}
            }}
            Provide at least 3 logical phases.
            """
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            roadmap_result = json.loads(response.text.strip())
        except Exception as e:
            logger.error(f"Gemini Career Roadmap generation failed: {e}")
            roadmap_result = MOCK_ROADMAP_DATA

    # Insert into public.career_roadmaps
    record = {
        "user_id": uid,
        "goal": goal,
        "current_level": current_level,
        "roadmap_json": roadmap_result.get("roadmap_json", {})
    }

    def db_insert():
        res = supabase_admin.table("career_roadmaps").insert(record).execute()
        return res.data[0] if res.data else record

    import uuid as uuid_lib
    import time
    def mock_insert():
        mock_record = dict(record)
        mock_record["id"] = str(uuid_lib.uuid4())
        mock_record["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        MOCK_ROADMAP_DB[mock_record["id"]] = mock_record
        return mock_record

    try:
        saved_record = handle_supabase_op(db_insert, mock_insert)
        return jsonify(saved_record), 200
    except Exception as db_err:
        logger.error(f"Failed to save career roadmap: {db_err}")
        return jsonify({"error": "Failed to save career roadmap to database."}), 500


@roadmap_bp.route('/api/roadmap/latest', methods=['GET'])
def get_latest_roadmap():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    def db_select_latest():
        res = supabase_admin.table("career_roadmaps").select("*").eq("user_id", uid).order("created_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None

    def mock_select_latest():
        user_roadmaps = [r for r in MOCK_ROADMAP_DB.values() if r["user_id"] == uid]
        if not user_roadmaps:
            return None
        sorted_roadmaps = sorted(user_roadmaps, key=lambda x: x.get("created_at", ""), reverse=True)
        return sorted_roadmaps[0]

    try:
        latest = handle_supabase_op(db_select_latest, mock_select_latest)
        if not latest:
            return jsonify({"message": "No career roadmaps found."}), 404
        return jsonify(latest), 200
    except Exception as e:
        logger.error(f"Failed to retrieve roadmap: {e}")
        return jsonify({"error": "Failed to retrieve roadmap."}), 500
