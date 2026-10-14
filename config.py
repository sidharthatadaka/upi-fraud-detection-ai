import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / '.env')

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'upi-fraud-ai-secret-default-2026')
    DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')
    PORT = int(os.getenv('PORT', 5000))
    
    # Database Settings
    DB_TYPE = os.getenv('DB_TYPE', 'mysql').lower()
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME', 'upi_fraud_db')
    
    # Serverless (Vercel) detection: root filesystem is read-only, use /tmp
    IS_VERCEL = bool(os.getenv('VERCEL'))
    if IS_VERCEL:
        SQLITE_DB_PATH = '/tmp/upi_fraud.db'
        UPLOAD_FOLDER = '/tmp/uploads'
    else:
        SQLITE_DB_PATH = str(BASE_DIR / os.getenv('SQLITE_DB_PATH', 'upi_fraud.db'))
        UPLOAD_FOLDER = str(BASE_DIR / os.getenv('UPLOAD_FOLDER', 'uploads'))
    
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'txt', 'webp'}
    
    # Risk Scoring Thresholds
    RISK_THRESHOLD_LOW = int(os.getenv('RISK_THRESHOLD_LOW', 35))
    RISK_THRESHOLD_HIGH = int(os.getenv('RISK_THRESHOLD_HIGH', 70))
    AUTO_BLOCK_HIGH_RISK = os.getenv('AUTO_BLOCK_HIGH_RISK', 'true').lower() in ('true', '1', 't')
