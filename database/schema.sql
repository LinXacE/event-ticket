-- Event Access Management System Database Schema
-- MySQL Database

CREATE DATABASE IF NOT EXISTS event_ticket_system;
USE event_ticket_system;

-- Users Table
CREATE TABLE users (
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
CREATE TABLE events (
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
CREATE TABLE pass_types (
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
('Guest', 'Limited guest access', 1, '#6c757d');

-- Event Passes Table
CREATE TABLE event_passes (
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
CREATE TABLE validation_logs (
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

-- Analytics Table
CREATE TABLE event_analytics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    total_passes_generated INT DEFAULT 0,
    total_passes_validated INT DEFAULT 0,
    judges_count INT DEFAULT 0,
    mentors_count INT DEFAULT 0,
    participants_count INT DEFAULT 0,
    volunteers_count INT DEFAULT 0,
    guests_count INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    INDEX idx_event (event_id)
);

-- System Settings Table
CREATE TABLE system_settings (
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
('pass_expiry_days', '30', 'Default pass expiry in days');

-- Create default admin user (password: admin123)
INSERT INTO users (username, email, password_hash, full_name, role) VALUES
('admin', 'admin@eventticket.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5lWqVcXzF4tXC', 'System Administrator', 'admin');
