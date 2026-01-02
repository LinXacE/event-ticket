from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from database import db
from flask_login  import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
# app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))

# Initialize extensions
db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# User loader function
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Import routes after app initialization
from routes import auth, events, passes, validation, analytics, dashboard, tickets, gates

# Register blueprints
app.register_blueprint(auth.bp)
app.register_blueprint(events.events_bp)
app.register_blueprint(passes.bp)
app.register_blueprint(validation.validation_bp)
app.register_blueprint(analytics.bp)
app.register_blueprint(dashboard.bp)
app.register_blueprint(tickets.tickets_bp)
app.register_blueprint(gates.bp)

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    return redirect(url_for('auth.login'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.context_processor
def utility_processor():
    def format_datetime(value, format='%Y-%m-%d %H:%M'):
        if value is None:
            return ''
        return value.strftime(format)
    return dict(format_datetime=format_datetime)

if __name__ == '__main__':
    # Create directories if they don't exist
    os.makedirs(os.getenv('QR_CODE_DIR', 'static/qr_codes'), exist_ok=True)
    os.makedirs(os.getenv('BARCODE_DIR', 'static/barcodes'), exist_ok=True)
    os.makedirs(os.getenv('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)
    
    app.run(debug=os.getenv('DEBUG', 'True') == 'True', host='0.0.0.0', port=5000)
