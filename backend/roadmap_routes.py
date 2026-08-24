import os
import json
import logging
import uuid
from flask import Blueprint, request, jsonify
from firebase_client import db
from resume_routes import get_auth_uid, handle_db_op

logger = logging.getLogger(__name__)

roadmap_bp = Blueprint('roadmap', __name__)

genai_module = None
genai_legacy_module = None

try:
    from google import genai
    genai_module = genai
except ImportError:
    pass

try:
    import google.generativeai as genai_legacy
    genai_legacy_module = genai_legacy
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
is_gemini_configured = bool(
    GEMINI_API_KEY 
    and not GEMINI_API_KEY.startswith("your-") 
    and not GEMINI_API_KEY.startswith("dummy") 
    and GEMINI_API_KEY != "your_gemini_api_key_here"
)

genai_client = None
genai_legacy_model = None

if is_gemini_configured:
    if genai_module is not None:
        try:
            genai_client = genai_module.Client(api_key=GEMINI_API_KEY)
        except Exception:
            pass
    if genai_client is None and genai_legacy_module is not None:
        try:
            genai_legacy_module.configure(api_key=GEMINI_API_KEY)
            genai_legacy_model = genai_legacy_module.GenerativeModel("gemini-3.6-flash")
        except Exception:
            is_gemini_configured = False

MOCK_ROADMAP_DB = {}

@roadmap_bp.route('/api/roadmap/generate', methods=['POST'])
def generate_roadmap():
    try:
        uid = get_auth_uid(request)
    except ValueError as val_err:
        return jsonify({"error": str(val_err)}), 401

    data = request.get_json() or {}
    goal = data.get("goal")
    current_level = data.get("current_level", "entry")

    if not goal:
        return jsonify({"error": "Missing goal (target career role) in request."}), 400

    if not is_gemini_configured or (not genai_client and not genai_legacy_model):
        return jsonify({"error": "AI analysis is temporarily unavailable. Please try again."}), 502

    try:
        prompt = f"""
        You are an expert career growth planner and technical mentor.
        Generate a detailed chronological step-by-step career path roadmap to achieve the target career goal: '{goal}', starting from experience level: '{current_level}'.
        Do not use predefined or hardcoded skill milestones. Infer relevant topics dynamically based on the target role '{goal}'.
        
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
        raw_text = ""
        if genai_client:
            resp = genai_client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            raw_text = resp.text or ""
        elif genai_legacy_model:
            resp = genai_legacy_model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            raw_text = resp.text or ""

        cleaned = raw_text.strip().replace("```json", "").replace("```", "").strip()
        roadmap_result = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Gemini Career Roadmap generation failed: {e}")
        return jsonify({"error": "AI analysis is temporarily unavailable. Please try again."}), 502

    r_id = str(uuid.uuid4())
    record = {
        "id": r_id,
        "user_id": uid,
        "goal": goal,
        "current_level": current_level,
        "roadmap_json": roadmap_result.get("roadmap_json", {})
    }

    def db_insert():
        db.collection("career_roadmaps").document(r_id).set(record)
        return record

    def mock_insert():
        MOCK_ROADMAP_DB[r_id] = record
        return record

    try:
        saved_record = handle_db_op(db_insert, mock_insert)
        return jsonify({
            "success": True,
            "roadmap_id": saved_record.get("id"),
            "goal": goal,
            "current_level": current_level,
            "roadmap": saved_record.get("roadmap_json")
        }), 201
    except Exception as save_err:
        logger.error(f"Failed to save career roadmap: {save_err}")
        return jsonify({"error": "Failed to save career roadmap."}), 500
