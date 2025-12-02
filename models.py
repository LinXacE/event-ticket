from database import db
from app import login_manager
from flask_login import UserMixin
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum('admin', 'organizer', 'security'), default='organizer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    events = db.relationship('Event', backref='organizer', lazy=True)
    validation_logs = db.relationship('ValidationLog', backref='validator', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Event(db.Model):
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(200), nullable=False)
    event_description = db.Column(db.Text)
    event_date = db.Column(db.Date, nullable=False)
    event_time = db.Column(db.Time, nullable=False)
    location = db.Column(db.String(255), nullable=False)
    total_capacity = db.Column(db.Integer, nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.Enum('active', 'completed', 'cancelled'), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    passes = db.relationship('EventPass', backref='event', lazy=True, cascade='all, delete-orphan')
    analytics = db.relationship('EventAnalytics', backref='event', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Event {self.event_name}>'

class PassType(db.Model):
    __tablename__ = 'pass_types'
    
    id = db.Column(db.Integer, primary_key=True)
    type_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    access_level = db.Column(db.Integer, default=1)
    color_code = db.Column(db.String(7), default='#007bff')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    passes = db.relationship('EventPass', backref='pass_type', lazy=True)
    
    def __repr__(self):
        return f'<PassType {self.type_name}>'

class EventPass(db.Model):
    __tablename__ = 'event_passes'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    pass_type_id = db.Column(db.Integer, db.ForeignKey('pass_types.id'), nullable=False)
    pass_code = db.Column(db.String(255), unique=True, nullable=False)
    encrypted_data = db.Column(db.Text, nullable=False)
    participant_name = db.Column(db.String(100), nullable=False)
    participant_email = db.Column(db.String(100))
    participant_phone = db.Column(db.String(20))
    qr_code_path = db.Column(db.String(255))
    barcode_path = db.Column(db.String(255))
    is_validated = db.Column(db.Boolean, default=False)
    validation_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    
    validation_logs = db.relationship('ValidationLog', backref='pass', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<EventPass {self.pass_code}>'

class ValidationLog(db.Model):
    __tablename__ = 'validation_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    pass_id = db.Column(db.Integer, db.ForeignKey('event_passes.id'), nullable=False)
    validator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    validation_time = db.Column(db.DateTime, default=datetime.utcnow)
    validation_status = db.Column(db.Enum('success', 'failed', 'duplicate'), nullable=False)
    validation_message = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    
    def __repr__(self):
        return f'<ValidationLog {self.id} - {self.validation_status}>'

class EventAnalytics(db.Model):
    __tablename__ = 'event_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    total_passes_generated = db.Column(db.Integer, default=0)
    total_passes_validated = db.Column(db.Integer, default=0)
    judges_count = db.Column(db.Integer, default=0)
    mentors_count = db.Column(db.Integer, default=0)
    participants_count = db.Column(db.Integer, default=0)
    volunteers_count = db.Column(db.Integer, default=0)
    guests_count = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<EventAnalytics Event:{self.event_id}>'

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemSetting {self.setting_key}>'
