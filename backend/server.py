import os
import sys
import logging
from flask import Flask, request, jsonify, send_from_directory

# Ensure backend directory and project root are in sys.path
backend_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from auth_routes import auth_bp
from resume_routes import resume_bp
from analysis_routes import analysis_bp
from ats_routes import ats_bp
from jobmatch_routes import jobmatch_bp
from interview_routes import interview_bp
from roadmap_routes import roadmap_bp
from chat_routes import chat_bp
from backend.app.blueprints.ai import ai_bp
from career_goal_routes import career_goal_bp
from profile_routes import profile_bp
from assessment_routes import assessment_bp
from learning_plan_routes import learning_plan_bp
from knowledge_assessment_routes import knowledge_assessment_bp
from recommendation_routes import recommendation_bp
from resume_builder_routes import resume_builder_bp
from job_opportunities import jobs_bp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

app = Flask(__name__, static_folder=frontend_dir, static_url_path='')

# Configure maximum file upload size (5MB)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Ensure uploads root directory exists
uploads_path = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(uploads_path, exist_ok=True)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(resume_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(ats_bp)
app.register_blueprint(jobmatch_bp)
app.register_blueprint(interview_bp)
app.register_blueprint(roadmap_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(career_goal_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(assessment_bp)
app.register_blueprint(learning_plan_bp)
app.register_blueprint(knowledge_assessment_bp)
app.register_blueprint(recommendation_bp)
app.register_blueprint(resume_builder_bp)
app.register_blueprint(jobs_bp)

# Custom CORS Handlers
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGIN", "").split(",") if o.strip()]

@app.before_request
def before_request():
    if request.method == "OPTIONS":
        return "", 204

@app.after_request
def after_request(response):
    origin = request.headers.get("Origin")
    if origin:
        if not ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS or origin in ALLOWED_ORIGINS or origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:") or ".vercel.app" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers.add("Access-Control-Allow-Origin", "*")
        
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response

# Static & Frontend Routing
@app.route('/', methods=['GET'])
def index():
    index_path = os.path.join(frontend_dir, 'index.html')
    if os.path.exists(index_path) and 'application/json' not in request.headers.get('Accept', ''):
        return send_from_directory(frontend_dir, 'index.html')
    return jsonify({
        "service": "CareerPilot AI Backend API",
        "status": "online",
        "health_check": "/api/health",
        "version": "1.0.0"
    }), 200

@app.route('/favicon.ico', methods=['GET'])
def favicon():
    fav_path = os.path.join(frontend_dir, 'favicon.ico')
    if os.path.exists(fav_path):
        return send_from_directory(frontend_dir, 'favicon.ico')
    return "", 204

@app.route('/api/health', methods=['GET'])
def health():
    try:
        from firebase_client import is_firebase_configured
    except Exception:
        is_firebase_configured = False
    
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_configured = bool(gemini_key and not gemini_key.startswith("YOUR_"))

    return jsonify({
        "success": True,
        "service": "CareerPilot AI Backend",
        "status": "healthy",
        "firebase_configured": is_firebase_configured,
        "gemini_configured": gemini_configured
    }), 200

@app.route('/<path:path>', methods=['GET'])
def serve_static(path):
    # Do not intercept API requests
    if path.startswith('api/'):
        return jsonify({"error": "Resource not found"}), 404
        
    full_path = os.path.join(frontend_dir, path)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory(frontend_dir, path)
        
    # Check if adding .html resolves the file (e.g. /dashboard -> dashboard.html)
    if not path.endswith('.html'):
        html_path = path + '.html'
        if os.path.exists(os.path.join(frontend_dir, html_path)):
            return send_from_directory(frontend_dir, html_path)
            
    return jsonify({"error": f"File not found: {path}"}), 404

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    logger.info(f"Starting CareerPilot Auth API on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
