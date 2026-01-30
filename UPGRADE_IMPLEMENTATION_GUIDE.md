# University-Level Upgrade Implementation Guide

## Overview
This guide provides step-by-step instructions to implement the new university-level features added to your event-ticket system.

## New Features Added

### 1. **Role-Based Access Control (RBAC)**
- Admin dashboard with full system oversight
- User management (create, update, delete users and assign roles)
- Three roles: `admin`, `organizer`, `security`
- Route protection decorators

### 2. **Multiple Ticket Types Per Event**
- Support for VIP, Normal, Student, Early Bird tickets
- Price management (ready for future payment integration)
- Quantity limits per type
- Color-coded tickets

### 3. **Enhanced Validation & Check-In**
- Gate-aware ticket scanning
- Detailed validation logs
- Status tracking (success, duplicate, expired, failed)

### 4. **Analytics & Reports Dashboard**
- Event-level analytics snapshots
- Scan statistics by gate and ticket type
- No-show tracking
- Peak scan hour identification

---

## Implementation Steps

### Step 1: Update Your Local Repository

```bash
cd event-ticket
git pull origin main
```

### Step 2: Create Database Migration

Create a new file `database/migrations/add_university_features.sql`:

```sql
-- Add ticket_types table
CREATE TABLE IF NOT EXISTS ticket_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    type_name VARCHAR(100) NOT NULL,
    description TEXT,
    max_quantity INT NOT NULL,
    quantity_generated INT DEFAULT 0,
    price FLOAT DEFAULT 0.0,
    color_code VARCHAR(7) DEFAULT '#007bff',
    access_level INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- Add ticket_validation_logs table
CREATE TABLE IF NOT EXISTS ticket_validation_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT NOT NULL,
    event_id INT NOT NULL,
    validator_id INT NOT NULL,
    gate_name VARCHAR(100),
    validation_status ENUM('success', 'failed', 'duplicate', 'expired') DEFAULT 'success',
    validation_message TEXT,
    validation_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (validator_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Add event_analytics_snapshots table
CREATE TABLE IF NOT EXISTS event_analytics_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    total_tickets_generated INT DEFAULT 0,
    total_tickets_scanned INT DEFAULT 0,
    no_show_count INT DEFAULT 0,
    duplicate_attempts INT DEFAULT 0,
    scan_by_gate JSON,
    scan_by_type JSON,
    peak_scan_hour VARCHAR(5),
    captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- Modify tickets table to add ticket_type_id and scanned_gate
ALTER TABLE tickets 
ADD COLUMN ticket_type_id INT AFTER batch_id,
ADD COLUMN scanned_gate VARCHAR(100) AFTER scanned_by,
ADD FOREIGN KEY (ticket_type_id) REFERENCES ticket_types(id) ON DELETE SET NULL;
```

### Step 3: Run Database Migration

Connect to your MySQL database and run:

```bash
mysql -u your_username -p your_database < database/migrations/add_university_features.sql
```

### Step 4: Register New Blueprints in `app.py`

Add these imports at the top of `app.py`:

```python
from routes.rbac import rbac_bp
from routes.ticket_types import ticket_types_bp
```

Then register the blueprints:

```python
app.register_blueprint(rbac_bp)
app.register_blueprint(ticket_types_bp)
```

### Step 5: Create Admin Template Files

Create directory structure:

```bash
mkdir -p templates/admin
mkdir -p templates/ticket_types
```

Create `templates/admin/dashboard.html` (basic template):

```html
{% extends 'base.html' %}
{% block content %}
<div class="container mt-4">
    <h1>Admin Dashboard</h1>
    
    <div class="row mt-4">
        <div class="col-md-3">
            <div class="card text-white bg-primary">
                <div class="card-body">
                    <h5>Total Users</h5>
                    <h2>{{ stats.total_users }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-success">
                <div class="card-body">
                    <h5>Total Events</h5>
                    <h2>{{ stats.total_events }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-info">
                <div class="card-body">
                    <h5>Total Tickets</h5>
                    <h2>{{ stats.total_tickets }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card text-white bg-warning">
                <div class="card-body">
                    <h5>Scan Rate</h5>
                    <h2>{{ stats.scan_rate }}</h2>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

### Step 6: Test the New Features

1. **Test RBAC**: 
   - Log in as admin
   - Visit `/admin/dashboard`
   - Try accessing `/admin/users` to manage user roles

2. **Test Ticket Types**:
   - Create an event as organizer
   - Visit `/ticket-types/event/<event_id>`
   - Add VIP, Normal, and Student ticket types

3. **Test Validation**:
   - Generate tickets with different types
   - Scan tickets and verify gate tracking works

---

## Testing Checklist

- [ ] Database migrations run successfully
- [ ] Admin dashboard loads correctly
- [ ] User role assignment works
- [ ] Ticket types can be created per event
- [ ] Tickets are linked to ticket types
- [ ] Validation logs capture gate information
- [ ] Analytics data is being collected

---

## Troubleshooting

### Issue: "Table already exists" error
**Solution**: Add `IF NOT EXISTS` to CREATE TABLE statements

### Issue: Routes not found (404)
**Solution**: Verify blueprints are registered in `app.py`

### Issue: Import errors for decorators
**Solution**: Ensure `utils/decorators.py` exists and contains the role_required function

---

## Next Steps (Future Enhancements)

1. **Payment Integration**: Connect ticket types to payment gateways
2. **Email Notifications**: Send tickets via email with QR codes
3. **Mobile App**: Build companion mobile app for guards
4. **Real-time Dashboard**: Add WebSocket support for live updates
5. **Advanced Analytics**: Add Chart.js visualizations

---

## Support

For questions or issues, refer to:
- `README.md` - Project overview
- `REFACTORING_GUIDE.md` - Code structure guide
- `BUGFIX_SUMMARY.md` - Known issues and fixes
