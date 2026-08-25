"""
CareerPilot AI — Flask Application Entry Point
Supports running directly via `python backend/app.py` or `python -m backend.server`.
"""
import os
import sys

# Ensure both backend dir and project root are in sys.path
backend_dir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.abspath(os.path.join(backend_dir, '..'))

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import logging
try:
    from server import app, logger
except ImportError:
    from backend.server import app, logger

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"
    logger.info(f"Starting CareerPilot Auth API on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
