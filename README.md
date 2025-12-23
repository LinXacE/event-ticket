# Event Access Control System with Automated QR/Barcode Verification

## Project Description

The Event Access Control System with Automated QR/Barcode Verification is a comprehensive web-based platform built with HTML, CSS, JavaScript, Python (Flask), and MySQL that manages the complete lifecycle of event access control—from ticket creation to real-time validation and analytics. 

The system generates secure, encrypted QR codes and barcodes that can be delivered as digital e-tickets or printed as physical passes (PNG/PDF format). Built-in webcam/scanner integration enables instant validation at multiple entry points, with real-time tracking to prevent duplicate entries and unauthorized access. 

The platform supports complex event scenarios including multi-gate access control (VIP entrance, Staff gate, General entrance), offline validation mode for areas with poor connectivity, and comprehensive analytics with CSV export capabilities.

## Key Features

### 1. User Authentication System
Secure login and registration functionality for event organizers, security staff, and administrators with role-based access control for different permission levels.

### 2. Event Management Module
Create, edit, and manage events with detailed configurations including:
- Event name
- Date and time
- Venue location
- Participant categories
- Access rules for different entry points

### 3. Automated Ticket Generation System
- Generate encrypted QR codes and barcodes with unique identifiers for each ticket
- Support multiple output formats: PNG images, PDF documents, or digital e-tickets
- Batch ticket creation for multiple participants simultaneously
- Tickets can be printed on physical cards/paper or distributed digitally
- Secret key-based encryption to prevent ticket duplication and fraud

**Ticket Creation Process:**
- System generates unique QR/barcode for each ticket with encrypted participant data
- Output options: PNG (for printing on cards), PDF (for attachments), or web-based e-ticket
- Each ticket contains: Event ID, Participant ID, Access Level, Expiration Time, Encrypted Security Key

### 4. Multi-Gate Access Control
- Configure multiple entry points: Gate A, Gate B, VIP entrance, Staff gate, Participant entrance
- Role-specific access permissions (judges access VIP gate, volunteers access staff gate, etc.)
- Gate-by-gate validation logic to ensure participants enter through correct gates
- Real-time gate status monitoring

### 5. Real-time Validation Scanner
- Built-in webcam/scanner integration for ticket scanning
- Instant QR code and barcode decryption and verification
- Validation checks:
  - ✓ Ticket exists in database?
  - ✓ Not expired?
  - ✓ Not already used?
  - ✓ Correct gate?
- Visual feedback (green for valid, red for invalid) with audio alerts
- Duplicate entry detection and prevention with immediate alerts
- Works with both webcam and dedicated barcode scanners

**Validation Process:**
- Security staff opens scanner interface on any device with webcam
- Scanner captures QR/barcode from physical pass or mobile screen
- System decrypts code and performs validation checks
- If all checks pass: Green screen + "Entry Approved" + logs entry with timestamp
- If any check fails: Red screen + Specific error message + Alert notification

### 6. Offline Validation Mode
- Download encrypted ticket database for offline validation
- Validate tickets without internet connection at remote entry points
- Sync validation logs when connection is restored
- Emergency backup validation system

### 7. Real-time Tracking Dashboard
- Live check-in counter showing current attendance vs. total tickets
- Real-time list of scanned users with timestamps
- Gate-by-gate breakdown showing entries per location
- Duplicate attempt alerts and suspicious activity notifications
- Entry status tracking (pending, checked-in, rejected)
- Live updates without page refresh

**Duplicate Detection:**
- System logs every scan attempt with timestamp
- Alerts triggered if same ticket scanned twice within configurable time window
- Dashboard shows duplicate attempts in real-time for security monitoring

### 8. Analytics and Reporting
- Visual analytics displaying attendance statistics and entry patterns
- Pass validation rates and rejection reasons
- Time-based entry graphs (peak entry times, hourly breakdown)
- Gate utilization reports
- CSV Export functionality for all data:
  - Attendee lists
  - Validation logs
  - Gate statistics
- Downloadable reports for post-event analysis

### 9. Secure Database Management
MySQL-based storage system for:
- Participant records
- Ticket data
- Validation logs
- Entry timestamps
- Gate access records
- Encrypted sensitive information
- Backup capabilities

## Technologies Used

- **Frontend**: HTML, CSS, JavaScript
- **Backend**: Python (Flask)
- **Database**: MySQL
- **QR/Barcode Generation**: Python libraries (qrcode, python-barcode)
- **Encryption**: Secret key-based encryption
- **Scanner Integration**: Webcam API / Hardware scanner support

## Installation

1. Clone the repository:
```bash
git clone https://github.com/LinXacE/event-ticket.git
cd event-ticket
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the database:
- Create a MySQL database
- Update database credentials in `.env` file

4. Run the application:
```bash
python app.py
```

5. Access the application at `http://localhost:5000`

## Usage

### For Event Organizers:
1. Log in to the system
2. Create a new event with details
3. Generate tickets for participants
4. Configure access gates and permissions
5. Download tickets in preferred format (PNG/PDF)
6. Distribute tickets to participants

### For Security Staff:
1. Log in to scanner interface
2. Select entry gate
3. Scan QR/barcode from participant's ticket
4. System validates and displays result
5. Monitor real-time dashboard for suspicious activity

### For Administrators:
1. Access analytics dashboard
2. Monitor real-time attendance
3. View gate-by-gate statistics
4. Export data as CSV for analysis
5. Generate post-event reports

## Security Features

- Encrypted QR codes and barcodes
- Secret key-based ticket generation
- Role-based access control
- Duplicate entry prevention
- Real-time security alerts
- Secure database storage

## Future Enhancements

- Mobile app for ticket scanning
- Advanced analytics with machine learning
- Integration with third-party ticketing platforms
- Biometric verification support
- Multi-language support

## License

This project is for educational purposes.

## Contact

For questions or support, please contact the repository maintainer.
