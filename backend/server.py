import os
import sys
import time
import logging
from collections import defaultdict
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

app = Flask(__name__, static_folder=frontend_dir, static_url_path='')

# Security: Configure maximum request / file upload size (5MB)
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

# -------------------------------------------------------------
# Production Security: Origin Validation & CORS
# -------------------------------------------------------------
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGIN", "").split(",") if o.strip()]

def is_allowed_origin(origin):
    if not origin:
        return False
    if not ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS:
        return True
    if origin in ALLOWED_ORIGINS:
        return True
    if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
        return True
    if origin.endswith(".vercel.app") or ".vercel.app" in origin:
        return True
    return False

# -------------------------------------------------------------
# Production Security: In-Memory Sliding Window Rate Limiter
# -------------------------------------------------------------
_RATE_LIMIT_STORE = defaultdict(list)
_RATE_LIMIT_AI_STORE = defaultdict(list)

# Limits: 120 API requests/min general, 30 AI generation requests/min
GENERAL_RATE_LIMIT = 120
AI_RATE_LIMIT = 30
RATE_LIMIT_WINDOW = 60  # seconds

def get_client_identifier():
    # Use Authorization token hash or client IP
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[-16:]
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")

@app.before_request
def handle_options_preflight_and_rate_limiting():
    # 1. Handle CORS Preflight immediately
    if request.method == "OPTIONS":
        origin = request.headers.get("Origin", "")
        res = app.make_response(("", 204))
        if is_allowed_origin(origin):
            res.headers["Access-Control-Allow-Origin"] = origin
            res.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            res.headers["Access-Control-Allow-Origin"] = origin if origin else "*"
        res.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
        res.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        res.headers["Access-Control-Max-Age"] = "86400"
        return res

    # 2. Rate Limiting on API endpoints
    path = request.path
    if path.startswith("/api/") and path != "/api/health":
        now = time.time()
        client_id = get_client_identifier()
        
        # Check AI endpoints limit
        is_ai_endpoint = any(kw in path for kw in [
            "/generate", "/analyze", "/chat", "/ai-suggest", "/recommendations/generate"
        ])
        
        if is_ai_endpoint:
            timestamps = [t for t in _RATE_LIMIT_AI_STORE[client_id] if now - t < RATE_LIMIT_WINDOW]
            if len(timestamps) >= AI_RATE_LIMIT:
                logger.warning(f"Rate limit exceeded on AI endpoint for client {client_id}")
                return jsonify({
                    "error": "Too many requests. Please wait a moment before trying again.",
                    "retry_after": int(RATE_LIMIT_WINDOW - (now - timestamps[0]))
                }), 429
            timestamps.append(now)
            _RATE_LIMIT_AI_STORE[client_id] = timestamps

        # Check General API limit
        gen_timestamps = [t for t in _RATE_LIMIT_STORE[client_id] if now - t < RATE_LIMIT_WINDOW]
        if len(gen_timestamps) >= GENERAL_RATE_LIMIT:
            logger.warning(f"Rate limit exceeded on API for client {client_id}")
            return jsonify({
                "error": "Rate limit exceeded. Please slow down.",
                "retry_after": int(RATE_LIMIT_WINDOW - (now - gen_timestamps[0]))
            }), 429
        gen_timestamps.append(now)
        _RATE_LIMIT_STORE[client_id] = gen_timestamps

# -------------------------------------------------------------
# Production Security: Response Headers & Hardening
# -------------------------------------------------------------
@app.after_request
def after_request(response):
    origin = request.headers.get("Origin")
    if origin:
        if is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        else:
            response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
        
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"

    # Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response

# -------------------------------------------------------------
# Production Security: Safe Global Error Handlers
# -------------------------------------------------------------
@app.errorhandler(400)
def bad_request_error(e):
    return jsonify({"error": "Bad request. Please verify your input."}), 400

@app.errorhandler(404)
def not_found_error(e):
    return jsonify({"error": "Requested resource was not found."}), 404

@app.errorhandler(413)
def payload_too_large_error(e):
    return jsonify({"error": "File or payload exceeds maximum allowed size of 5 MB."}), 413

@app.errorhandler(429)
def too_many_requests_error(e):
    return jsonify({"error": "Too many requests. Please slow down and try again later."}), 429

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({"error": "An unexpected server error occurred. Please try again later."}), 500

# -------------------------------------------------------------
# Static & Frontend Routing
# -------------------------------------------------------------
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
    # Production security: Debug mode is only enabled when explicitly set to development
    debug = os.getenv("FLASK_ENV") == "development"
    logger.info(f"Starting CareerPilot Backend on port {port} (debug={debug})...")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
