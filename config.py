"""Application Configuration Module

Handles all application configuration settings including database, security,
and feature flags. Supports multiple environments (development, testing, production).
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration class"""
    
    # Application Settings
    DEBUG = False
    TESTING = False
    
    # Security Settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-key-change-in-production')
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    
    # Database Configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
    }
    
    # Upload Configuration
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))  # 16MB
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    QR_CODE_DIR = os.getenv('QR_CODE_DIR', 'static/qr_codes')
    BARCODE_DIR = os.getenv('BARCODE_DIR', 'static/barcodes')
    
    # QR Code Settings
    QR_CODE_SIZE = int(os.getenv('QR_CODE_SIZE', 200))
    QR_CODE_VERSION = int(os.getenv('QR_CODE_VERSION', 1))
    
    # Barcode Settings
    BARCODE_FORMAT = os.getenv('BARCODE_FORMAT', 'code128')
    
    # Validation Settings
    DUPLICATE_CHECK_WINDOW_MINUTES = int(os.getenv('DUPLICATE_CHECK_WINDOW', 5))
    OFFLINE_MODE_ENABLED = os.getenv('OFFLINE_MODE_ENABLED', 'True') == 'True'
    
    # Email Settings
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@event-ticket.com')
    
    # Feature Flags
    ENABLE_API_LOGGING = os.getenv('ENABLE_API_LOGGING', 'True') == 'True'
    ENABLE_ANALYTICS = os.getenv('ENABLE_ANALYTICS', 'True') == 'True'
    ENABLE_NOTIFICATIONS = os.getenv('ENABLE_NOTIFICATIONS', 'True') == 'True'


class DevelopmentConfig(Config):
    """Development environment configuration"""
    
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DEV_DATABASE_URL',
        'sqlite:///site.db'
    )
    SQLALCHEMY_ECHO = True


class TestingConfig(Config):
    """Testing environment configuration"""
    
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production environment configuration"""
    
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """Get configuration object for the specified environment"""
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, DevelopmentConfig)
