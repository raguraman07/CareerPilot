import os
import logging
from flask import Flask, request, jsonify
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

app = Flask(__name__)

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
# We implement CORS manually using Flask middleware to avoid external package dependencies
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

# Server-side auth split rationale:
# Although the frontend JS client can call Supabase Auth APIs directly (which is standard practice),
# this Flask API serves three critical purposes:
# 1. Enforcing server-side validation and sanitization of user data (e.g. sanitizing profiles' full_name)
# 2. Acting as a secure admin client (using service_role) to insert/modify user profile data
# 3. Providing token verification endpoints for future backend-rendered pages or services.

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "careercopilot-auth-api"}), 200

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    logger.info(f"Starting CareerPilot Auth API on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=debug)