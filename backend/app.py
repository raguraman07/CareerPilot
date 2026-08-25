"""
CareerPilot AI — Flask Application Entry Point Wrapper
Re-exports the Flask application instance from backend.server to support legacy `python backend/app.py` execution.
"""
import os
import logging
from backend.server import app, logger

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    logger.info(f"Starting CareerPilot Auth API on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
