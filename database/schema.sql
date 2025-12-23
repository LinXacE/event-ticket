-- Event Access Management System Database Schema
-- MySQL Database

CREATE DATABASE IF NOT EXISTS event_ticket_system;
USE event_ticket_system;

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('admin', 'organizer', 'security') DEFAULT 'organizer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    INDEX idx_email (email),
    INDEX idx_username (username)
);

-- Events Table
CREATE TABLE IF NOT EXISTS events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_name VARCHAR(200) NOT NULL,
    event_description TEXT,
    event_date DATE NOT NULL,
    event_time TIME NOT NULL,
    location VARCHAR(255) NOT NULL,
    total_capacity INT NOT NULL,
    organizer_id INT NOT NULL,
    status ENUM('active', 'completed', 'cancelled') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_event_date (event_date),
    INDEX idx_organizer (organizer_id)
);

-- Pass Types Table
CREATE TABLE IF NOT EXISTS pass_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type_name VARCHAR(50) NOT NULL,
    description TEXT,
    access_level INT DEFAULT 1,
    color_code VARCHAR(7) DEFAULT '#007bff',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default pass types
INSERT INTO pass_types (type_name, description, access_level, color_code) VALUES
('Judge', 'Full access pass for event judges', 5, '#dc3545'),
('Mentor', 'Access pass for mentors and advisors', 4, '#28a745'),
('Participant', 'Standard participant access', 3, '#007bff'),
('Volunteer', 'Volunteer staff access', 2, '#ffc107'),
('Guest', 'Limited guest access', 1, '#6c757d')
ON DUPLICATE KEY UPDATE type_name=type_name;

-- Event Passes Table
CREATE TABLE IF NOT EXISTS event_passes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    pass_type_id INT NOT NULL,
    pass_code VARCHAR(255) UNIQUE NOT NULL,
    encrypted_data TEXT NOT NULL,
    participant_name VARCHAR(100) NOT NULL,
    participant_email VARCHAR(100),
    participant_phone VARCHAR(20),
    qr_code_path VARCHAR(255),
    barcode_path VARCHAR(255),
    is_validated BOOLEAN DEFAULT FALSE,
    validation_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (pass_type_id) REFERENCES pass_types(id),
    INDEX idx_pass_code (pass_code),
    INDEX idx_event (event_id),
    INDEX idx_participant_email (participant_email)
);

-- Validation Logs Table
CREATE TABLE IF NOT EXISTS validation_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pass_id INT NOT NULL,
    validator_id INT NOT NULL,
    validation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    validation_status ENUM('success', 'failed', 'duplicate') NOT NULL,
    validation_message TEXT,
    ip_address VARCHAR(45),
    FOREIGN KEY (pass_id) REFERENCES event_passes(id) ON DELETE CASCADE,
    FOREIGN KEY (validator_id) REFERENCES users(id),
    INDEX idx_pass (pass_id),
    INDEX idx_validation_time (validation_time)
);

-- Analytics Table (UPDATED - removed fixed role fields)
CREATE TABLE IF NOT EXISTS event_analytics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    total_passes_generated INT DEFAULT 0,
    total_passes_validated INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    INDEX idx_event (event_id)
);

-- NEW: Ticket Batches Table (for Normal/Gamify seat management)
CREATE TABLE IF NOT EXISTS ticket_batches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    batch_name VARCHAR(100) NOT NULL,
    batch_type ENUM('normal', 'gamify') DEFAULT 'normal',
    seat_count INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    INDEX idx_event (event_id)
);

-- NEW: Promotions Table (for discounts and free items)
CREATE TABLE IF NOT EXISTS promotions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    promotion_name VARCHAR(100) NOT NULL,
    promotion_type ENUM('free_item', 'discount_percent', 'discount_amount') NOT NULL,
    value VARCHAR(100),
    quantity INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    INDEX idx_event (event_id)
);

-- NEW: Tickets Table (with barcode and QR scanner support)
CREATE TABLE IF NOT EXISTS tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id INT NOT NULL,
    ticket_code VARCHAR(255) UNIQUE NOT NULL,
    barcode VARCHAR(255) UNIQUE NOT NULL,
    status ENUM('available', 'used', 'expired') DEFAULT 'available',
    promotion_id INT,
    price FLOAT DEFAULT 0.0,
    scanned_by VARCHAR(100),
    scanned_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES ticket_batches(id) ON DELETE CASCADE,
    FOREIGN KEY (promotion_id) REFERENCES promotions(id),
    INDEX idx_batch (batch_id),
    INDEX idx_ticket_code (ticket_code)
);

-- System Settings Table
CREATE TABLE IF NOT EXISTS system_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Insert default system settings
INSERT INTO system_settings (setting_key, setting_value, description) VALUES
('encryption_key', 'CHANGE_THIS_SECRET_KEY_12345', 'Secret key for QR/Barcode encryption'),
('max_validation_attempts', '3', 'Maximum validation attempts per pass'),
('pass_expiry_days', '30', 'Default pass expiry in days')
ON DUPLICATE KEY UPDATE setting_key=setting_key;

-- Create default admin user (password: admin123)
INSERT INTO users (username, email, password_hash, full_name, role) VALUES
('admin', 'admin@eventticket.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5lWqVcXzF4tXC', 'System Administrator', 'admin')
ON DUPLICATE KEY UPDATE username=username;

-- Gates Table (Multi-Gate Access Control)
CREATE TABLE IF NOT EXISTS gates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    gate_name VARCHAR(100) NOT NULL,
    gate_type ENUM('VIP', 'Staff', 'General', 'Participant', 'Judge', 'Custom') DEFAULT 'General',
    gate_description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    INDEX idx_event (event_id),
    INDEX idx_gate_type (gate_type)
);

-- Gate Access Rules Table (Which pass types can access which gates)
CREATE TABLE IF NOT EXISTS gate_access_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    gate_id INT NOT NULL,
    pass_type_id INT NOT NULL,
    can_access BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gate_id) REFERENCES gates(id) ON DELETE CASCADE,
    FOREIGN KEY (pass_type_id) REFERENCES pass_types(id) ON DELETE CASCADE,
    UNIQUE KEY unique_gate_pass (gate_id, pass_type_id),
    INDEX idx_gate (gate_id),
    INDEX idx_pass_type (pass_type_id)
);

-- Gate Validation Logs Table (Track which gate each validation occurred at)
CREATE TABLE IF NOT EXISTS gate_validation_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    validation_log_id INT NOT NULL,
    gate_id INT NOT NULL,
    gate_access_granted BOOLEAN DEFAULT TRUE,
    gate_access_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (validation_log_id) REFERENCES validation_logs(id) ON DELETE CASCADE,
    FOREIGN KEY (gate_id) REFERENCES gates(id) ON DELETE CASCADE,
    INDEX idx_validation (validation_log_id),
    INDEX idx_gate (gate_id)
);

-- Offline Validation Queue Table (Store validations done offline)
CREATE TABLE IF NOT EXISTS offline_validation_queue (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pass_code VARCHAR(255) NOT NULL,
    validator_id INT NOT NULL,
    validation_status ENUM('success', 'failed', 'duplicate') NOT NULL,
    validation_message TEXT,
    gate_id INT,
    validation_time TIMESTAMP NOT NULL,
    sync_status ENUM('pending', 'synced', 'failed') DEFAULT 'pending',
    synced_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_pass_code (pass_code),
    INDEX idx_sync_status (sync_status),
    INDEX idx_validation_time (validation_time)
);

-- Duplicate Alert Settings Table (Configurable time windows)
CREATE TABLE IF NOT EXISTS duplicate_alert_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    time_window_minutes INT DEFAULT 5,
    alert_enabled BOOLEAN DEFAULT TRUE,
    notification_method ENUM('dashboard', 'email', 'both') DEFAULT 'dashboard',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    UNIQUE KEY unique_event (event_id)
);

-- Real-time Alerts Table (Store active alerts for dashboard)
CREATE TABLE IF NOT EXISTS realtime_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    alert_type ENUM('duplicate_entry', 'suspicious_activity', 'gate_violation', 'system_error') NOT NULL,
    alert_message TEXT NOT NULL,
    pass_id INT,
    gate_id INT,
    severity ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium',
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by INT,
    acknowledged_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (pass_id) REFERENCES event_passes(id) ON DELETE SET NULL,
    FOREIGN KEY (gate_id) REFERENCES gates(id) ON DELETE SET NULL,
    FOREIGN KEY (acknowledged_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_event (event_id),
    INDEX idx_alert_type (alert_type),
    INDEX idx_is_acknowledged (is_acknowledged),
    INDEX idx_created_at (created_at)
);
