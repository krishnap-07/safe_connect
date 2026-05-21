import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from database.db import init_db
from routes.incidents import incidents_bp

# Load environment variables
load_dotenv()

def create_app():
    # Trigger reload
    app = Flask(__name__)
    
    # Configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    
    # Paths
    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)
    
    # Use existing db or create one
    app.config["SQLITE_PATH"] = os.getenv("SQLITE_PATH", str(instance_path / "safe_connect.db"))
    
    upload_folder = Path(app.root_path) / "uploads"
    upload_folder.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = str(upload_folder)
    
    # Initialize database
    init_db(app.config["SQLITE_PATH"])
    
    # Register blueprints
    app.register_blueprint(incidents_bp)
    
    return app

app = create_app()

if __name__ == "__main__":
    debug = os.getenv("DEBUG", "true").lower() == "true"
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))
    app.run(debug=debug, host=host, port=port)
