import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask Config
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    
    # Database Config - Render provides DATABASE_URL
    if os.getenv('DATABASE_URL'):
        # For PostgreSQL on Render
        SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL').replace('postgres://', 'postgresql://')
    elif os.getenv('USE_SQLITE', 'true').lower() == 'true':
        # SQLite for local development (no MySQL needed)
        import os as os_module
        basedir = os_module.path.abspath(os_module.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os_module.path.join(basedir, 'app.db')}"
        print("Using SQLite database for local development")
    else:
        # Local MySQL fallback
        DB_HOST = os.getenv('DB_HOST', 'localhost')
        DB_USER = os.getenv('DB_USER', 'root')
        DB_PASSWORD = os.getenv('DB_PASSWORD', '')
        DB_NAME = os.getenv('DB_NAME', 'browser_extension')
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    
    # Gemini AI Config
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
    
    # CORS Config - UPDATED WITH YOUR ACTUAL VERCEL URL
    cors_origins_env = os.getenv('CORS_ORIGINS', '').strip()
    if cors_origins_env:
        CORS_ORIGINS = cors_origins_env.split(',')
    else:
        # Default origins - UPDATE THIS WITH YOUR ACTUAL VERCEL URL
        CORS_ORIGINS = [
            'https://extension-frontend-git-main-bathula-sai-kirans-projects.vercel.app',
            'https://extension-frontend-qfk87o3nu-bathula-sai-kirans-projects.vercel.app',
            'https://smartbrowse-ai.vercel.app',
            'http://localhost:3000',
            'chrome-extension://*',
        ]
    
    # Log CORS configuration on import
    print(f"CORS Origins configured: {CORS_ORIGINS}")
