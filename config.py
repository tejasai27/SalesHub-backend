import os
from dotenv import load_dotenv
import re

load_dotenv()

class Config:
    # Flask Config
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    
    # Database Config - SQLite for local development
    import os as os_module
    basedir = os_module.path.abspath(os_module.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os_module.path.join(basedir, 'app.db')}"
    print("Using SQLite database for local development")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    
    # Gemini AI Config
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = 'gemini-2.5-flash-lite'  # Lite version may have separate quota
    
    # CORS Config - Supports Chrome extensions and local development
    cors_origins_env = os.getenv('CORS_ORIGINS', '').strip()
    if cors_origins_env:
        CORS_ORIGINS = cors_origins_env.split(',')
    else:
        # Default origins for local development
        CORS_ORIGINS = [
            'http://localhost:3000',
            'http://localhost:5173',
            # Chrome extension origins - regex pattern for all extensions
            re.compile(r'^chrome-extension://.*$'),
            # Allow all origins for development (Chrome extension SWs may have null origin)
            '*',
        ]
    
    # Log CORS configuration on import
    print(f"CORS Origins configured: {CORS_ORIGINS}")

