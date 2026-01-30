"""Application Factory and Main Entry Point

Refactored Flask application factory pattern for better modularity,
testability, and maintainability.
"""

import os
import logging
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_bcrypt import Bcrypt
from config import get_config
from exceptions import EventTicketException

# Initialize extensions
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """Application factory function
    
    Args:
        config_name: Configuration environment (development, testing, production)
    
    Returns:
        Flask application instance
    """
    
    # Get configuration
    config = get_config(config_name)
    
    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # User loader
    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))
    
    # Register blueprints
    _register_blueprints(app)
    
    # Register error handlers
    _register_error_handlers(app)
    
    # Register context processors
    _register_context_processors(app)
    
    # Create upload directories
    _create_upload_directories(app)
    
    # Setup database
    with app.app_context():
        db.create_all()
        logger.info('Database initialized')
    
    logger.info(f'Application created with {config_name or "default"} configuration')
    return app


def _register_blueprints(app):
    """Register all application blueprints"""
    try:
        from routes import (
            auth, events, passes, validation, 
            analytics, dashboard, tickets, gates
        )
        
        blueprints = [
            (auth.bp, 'auth'),
            (events.events_bp, 'events'),
            (passes.bp, 'passes'),
            (validation.validation_bp, 'validation'),
            (analytics.bp, 'analytics'),
            (dashboard.bp, 'dashboard'),
            (tickets.tickets_bp, 'tickets'),
            (gates.bp, 'gates'),
        ]
        
        for blueprint, name in blueprints:
            app.register_blueprint(blueprint)
            logger.debug(f'Registered blueprint: {name}')
    
    except ImportError as e:
        logger.error(f'Error registering blueprints: {e}')
        raise


def _register_error_handlers(app):
    """Register global error handlers"""
    
    @app.errorhandler(EventTicketException)
    def handle_event_ticket_exception(error):
        """Handle custom application exceptions"""
        logger.warning(f'Application error: {error.message}')
        return render_template(
            'errors/error.html',
            error=error.message,
            status_code=error.status_code
        ), error.status_code
    
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors"""
        logger.debug('404 Not Found error')
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle 403 Forbidden errors"""
        logger.warning('403 Forbidden error')
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server errors"""
        logger.error(f'500 Internal Server error: {error}')
        db.session.rollback()
        return render_template('errors/500.html'), 500


def _register_context_processors(app):
    """Register template context processors"""
    
    @app.context_processor
    def utility_processor():
        from datetime import datetime
        
        def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
            """Format datetime for templates"""
            if value is None:
                return ''
            if isinstance(value, str):
                return value
            return value.strftime(format)
        
        def format_date(value, format='%Y-%m-%d'):
            """Format date for templates"""
            if value is None:
                return ''
            return value.strftime(format)
        
        def is_admin():
            """Check if current user is admin"""
            return current_user.is_authenticated and current_user.role == 'admin'
        
        def is_organizer():
            """Check if current user is organizer"""
            return current_user.is_authenticated and current_user.role == 'organizer'
        
        return dict(
            format_datetime=format_datetime,
            format_date=format_date,
            is_admin=is_admin,
            is_organizer=is_organizer
        )


def _create_upload_directories(app):
    """Create required upload directories"""
    directories = [
        app.config.get('UPLOAD_FOLDER', 'static/uploads'),
        app.config.get('QR_CODE_DIR', 'static/qr_codes'),
        app.config.get('BARCODE_DIR', 'static/barcodes'),
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f'Directory created/exists: {directory}')


if __name__ == '__main__':
    # Create application
    app = create_app(os.getenv('FLASK_ENV', 'development'))
    
    # Run development server
    debug_mode = os.getenv('DEBUG', 'True') == 'True'
    app.run(
        debug=debug_mode,
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        use_reloader=debug_mode
    )
