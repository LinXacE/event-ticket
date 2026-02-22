from database import db
from flask_login import UserMixin
from datetime import datetime


# ================= USER MODEL =================

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)

    role = db.Column(db.Enum('admin', 'organizer', 'security', name='user_roles'), default='organizer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    events = db.relationship('Event', backref='organizer', lazy=True)
    validation_logs = db.relationship('ValidationLog', backref='validator', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'


# ================= EVENT MODEL =================

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
    status = db.Column(db.Enum('active', 'completed', 'cancelled', name='event_status'), default='active')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    passes = db.relationship('EventPass', backref='event', lazy=True, cascade='all, delete-orphan')
    analytics = db.relationship('EventAnalytics', backref='event', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Event {self.event_name}>'


# ================= PASS TYPE =================

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


# ================= EVENT PASS =================

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

    validation_logs = db.relationship('ValidationLog', backref='pass_obj', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<EventPass {self.pass_code}>'


# ================= VALIDATION LOG =================

class ValidationLog(db.Model):
    __tablename__ = 'validation_logs'

    id = db.Column(db.Integer, primary_key=True)
    pass_id = db.Column(db.Integer, db.ForeignKey('event_passes.id'), nullable=False)
    validator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    validation_time = db.Column(db.DateTime, default=datetime.utcnow)
    validation_status = db.Column(db.Enum('success', 'failed', 'duplicate', name='validation_status'), nullable=False)
    validation_message = db.Column(db.Text)
    ip_address = db.Column(db.String(45))

    def __repr__(self):
        return f'<ValidationLog {self.id} - {self.validation_status}>'


# ================= EVENT ANALYTICS =================

class EventAnalytics(db.Model):
    __tablename__ = 'event_analytics'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)

    total_passes_generated = db.Column(db.Integer, default=0)
    total_passes_validated = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<EventAnalytics Event:{self.event_id}>'


# ================= REALTIME ALERT =================

class RealtimeAlert(db.Model):
    __tablename__ = 'realtime_alerts'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)

    alert_type = db.Column(db.Enum('duplicate_entry', 'suspicious_activity', 'gate_violation', 'system_error', name='alert_types'), nullable=False)
    alert_message = db.Column(db.Text, nullable=False)

    pass_id = db.Column(db.Integer, db.ForeignKey('event_passes.id'))
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'))

    severity = db.Column(db.Enum('low', 'medium', 'high', 'critical', name='alert_severity'), default='medium')
    is_acknowledged = db.Column(db.Boolean, default=False)

    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    acknowledged_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<RealtimeAlert {self.alert_type} - {self.severity}>'


# ================= EVENT ANALYTICS SNAPSHOT =================

class EventAnalyticsSnapshot(db.Model):
    __tablename__ = 'event_analytics_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)

    total_tickets_generated = db.Column(db.Integer, default=0)
    total_tickets_scanned = db.Column(db.Integer, default=0)
    no_show_count = db.Column(db.Integer, default=0)
    duplicate_attempts = db.Column(db.Integer, default=0)

    # SQLite safe (use Text instead of JSON)
    scan_by_gate = db.Column(db.Text)
    scan_by_type = db.Column(db.Text)

    peak_scan_hour = db.Column(db.String(5))
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<EventAnalyticsSnapshot Event:{self.event_id}>'

# ================= TICKET BATCH =================

class TicketBatch(db.Model):
    __tablename__ = 'ticket_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    batch_name = db.Column(db.String(100), nullable=False)
    batch_type = db.Column(db.Enum('normal', 'gamify', name='batch_types'), default='normal')
    seat_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    tickets = db.relationship('Ticket', backref='batch', lazy=True)
    
    def __repr__(self):
        return f'<TicketBatch {self.batch_name}>'

# ================= PROMOTION =================

class Promotion(db.Model):
    __tablename__ = 'promotions'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    promotion_name = db.Column(db.String(100), nullable=False)
    promotion_type = db.Column(db.Enum('free_item', 'discount_percent', 'discount_amount', name='promotion_types'), nullable=False)
    value = db.Column(db.String(100))
    quantity = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    tickets = db.relationship('Ticket', backref='promotion', lazy=True)
    
    def __repr__(self):
        return f'<Promotion {self.promotion_name}>'

# ================= TICKET =================

class Ticket(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('ticket_batches.id'), nullable=False)
    ticket_code = db.Column(db.String(255), unique=True, nullable=False)
    barcode = db.Column(db.String(255), unique=True, nullable=False)
    status = db.Column(db.Enum('available', 'used', 'expired', name='ticket_status'), default='available')
    promotion_id = db.Column(db.Integer, db.ForeignKey('promotions.id'))
    price = db.Column(db.Float, default=0.0)
    scanned_by = db.Column(db.String(100))
    scanned_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Ticket {self.ticket_code}>'

# ================= GATE =================

class Gate(db.Model):
    __tablename__ = 'gates'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    gate_name = db.Column(db.String(100), nullable=False)
    gate_type = db.Column(db.Enum('VIP', 'Staff', 'General', 'Participant', 'Judge', 'Custom', name='gate_types'), default='General')
    gate_description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    access_rules = db.relationship('GateAccessRule', backref='gate', lazy=True, cascade='all, delete-orphan')
    validation_logs = db.relationship('GateValidationLog', backref='gate', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Gate {self.gate_name}>'

# ================= GATE ACCESS RULE =================

class GateAccessRule(db.Model):
    __tablename__ = 'gate_access_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'), nullable=False)
    pass_type_id = db.Column(db.Integer, db.ForeignKey('pass_types.id'), nullable=False)
    can_access = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Enables template access like rule.pass_type.type_name
    pass_type = db.relationship('PassType', backref=db.backref('gate_rules', lazy=True))
    
    def __repr__(self):
        return f'<GateAccessRule Gate:{self.gate_id} PassType:{self.pass_type_id}>'

# ================= GATE VALIDATION LOG =================

class GateValidationLog(db.Model):
    __tablename__ = 'gate_validation_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    validation_log_id = db.Column(db.Integer, db.ForeignKey('validation_logs.id'), nullable=False)
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'), nullable=False)
    gate_access_granted = db.Column(db.Boolean, default=True)
    gate_access_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GateValidationLog {self.id}>'


# ================= TICKET GATE VALIDATION LOG =================

class TicketGateValidationLog(db.Model):
    __tablename__ = 'ticket_gate_validation_logs'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'), nullable=False)
    validator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    validation_status = db.Column(
        db.Enum('success', 'failed', 'duplicate', name='ticket_gate_validation_status'),
        nullable=False
    )
    validation_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship(
        'Ticket',
        backref=db.backref('gate_validation_logs', lazy=True, cascade='all, delete-orphan')
    )
    gate = db.relationship(
        'Gate',
        backref=db.backref('ticket_validation_logs', lazy=True, cascade='all, delete-orphan')
    )
    validator = db.relationship(
        'User',
        backref=db.backref('ticket_validation_logs', lazy=True)
    )

    def __repr__(self):
        return f'<TicketGateValidationLog Ticket:{self.ticket_id} Gate:{self.gate_id} Status:{self.validation_status}>'


# ================= EVENT SCANNER ASSIGNMENT =================

class EventScannerAssignment(db.Model):
    __tablename__ = 'event_scanner_assignments'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    scanner_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'))
    assigned_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    event = db.relationship('Event', backref=db.backref('scanner_assignments', lazy=True, cascade='all, delete-orphan'))
    scanner_user = db.relationship('User', foreign_keys=[scanner_user_id], backref=db.backref('scanner_assignments', lazy=True))
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_user_id], backref=db.backref('created_scanner_assignments', lazy=True))
    gate = db.relationship('Gate', backref=db.backref('scanner_assignments', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('event_id', 'scanner_user_id', 'gate_id', name='uq_event_scanner_gate'),
    )

    def __repr__(self):
        gate_text = self.gate_id if self.gate_id is not None else 'all-gates'
        return f'<EventScannerAssignment Event:{self.event_id} Scanner:{self.scanner_user_id} Gate:{gate_text}>'


# ================= EVENT SCANNER INVITE =================

class EventScannerInvite(db.Model):
    __tablename__ = 'event_scanner_invites'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    inviter_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invitee_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    gate_id = db.Column(db.Integer, db.ForeignKey('gates.id'))
    status = db.Column(
        db.Enum('pending', 'accepted', 'declined', 'cancelled', name='scanner_invite_status'),
        nullable=False,
        default='pending'
    )
    invite_message = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    responded_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    event = db.relationship('Event', backref=db.backref('scanner_invites', lazy=True, cascade='all, delete-orphan'))
    gate = db.relationship('Gate', backref=db.backref('scanner_invites', lazy=True))
    inviter = db.relationship('User', foreign_keys=[inviter_user_id], backref=db.backref('sent_scanner_invites', lazy=True))
    invitee = db.relationship('User', foreign_keys=[invitee_user_id], backref=db.backref('received_scanner_invites', lazy=True))

    def __repr__(self):
        gate_text = self.gate_id if self.gate_id is not None else 'all-gates'
        return f'<EventScannerInvite Event:{self.event_id} Invitee:{self.invitee_user_id} Gate:{gate_text} Status:{self.status}>'

# ================= OFFLINE VALIDATION QUEUE =================

class OfflineValidationQueue(db.Model):
    __tablename__ = 'offline_validation_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    pass_code = db.Column(db.String(255), nullable=False)
    validator_id = db.Column(db.Integer, nullable=False)
    validation_status = db.Column(db.Enum('success', 'failed', 'duplicate', name='offline_validation_status'), nullable=False)
    validation_message = db.Column(db.Text)
    gate_id = db.Column(db.Integer)
    validation_time = db.Column(db.DateTime, nullable=False)
    sync_status = db.Column(db.Enum('pending', 'synced', 'failed', name='sync_status'), default='pending')
    synced_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<OfflineValidationQueue {self.pass_code} - {self.sync_status}>'

# ================= DUPLICATE ALERT SETTING =================

class DuplicateAlertSetting(db.Model):
    __tablename__ = 'duplicate_alert_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    time_window_minutes = db.Column(db.Integer, default=5)
    alert_enabled = db.Column(db.Boolean, default=True)
    notification_method = db.Column(db.Enum('dashboard', 'email', 'both', name='notification_methods'), default='dashboard')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<DuplicateAlertSetting Event:{self.event_id}>'
