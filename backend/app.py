import os
import logging
from flask import Flask, request, jsonify, send_from_directory
from auth_routes import auth_bp
from resume_routes import resume_bp
from analysis_routes import analysis_bp
from ats_routes import ats_bp
from jobmatch_routes import jobmatch_bp
from interview_routes import interview_bp
from roadmap_routes import roadmap_bp
from chat_routes import chat_bp
from app.blueprints.ai import ai_bp

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

# Custom CORS Handlers
@app.before_request
def before_request():
    if request.method == "OPTIONS":
        return "", 204

@app.after_request
def after_request(response):
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
    return jsonify({"status": "healthy", "service": "careercopilot-auth-api"}), 200

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
    app.run(host="0.0.0.0", port=port, debug=debug)