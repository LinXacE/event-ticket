from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Event, TicketBatch, Ticket, Promotion
from database import db
from utils.barcode_generator import create_event_pass_barcode
import secrets
import string

tickets_bp = Blueprint('tickets', __name__, url_prefix='/tickets')

def generate_ticket_code(length=8):
    """Generate a random ticket code"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

@tickets_bp.route('/event/<int:event_id>')
@login_required
def list_tickets(event_id):
    """List all tickets for an event"""
    event = Event.query.get_or_404(event_id)
    
    # Check permission
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to view these tickets', 'error')
        return redirect(url_for('dashboard.home'))
    
    # Get all batches and tickets
    batches = TicketBatch.query.filter_by(event_id=event_id).all()
    tickets = []
    for batch in batches:
        tickets.extend(batch.tickets)
    
    return render_template('tickets/list.html', event=event, batches=batches, tickets=tickets)

@tickets_bp.route('/batch/create/<int:event_id>', methods=['GET', 'POST'])
@login_required
def create_batch(event_id):
    """Create a new ticket batch"""
    event = Event.query.get_or_404(event_id)
    
    # Check permission
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to create batches', 'error')
        return redirect(url_for('dashboard.home'))
    
    if request.method == 'POST':
        try:
            batch_name = request.form.get('batch_name')
            batch_type = request.form.get('batch_type', 'normal')
            seat_count = int(request.form.get('seat_count', 0))
            price = float(request.form.get('price', 0.0))
            
            # Create batch
            batch = TicketBatch(
                event_id=event_id,
                batch_name=batch_name,
                batch_type=batch_type,
                seat_count=seat_count
            )
            db.session.add(batch)
            db.session.flush()  # Get batch ID
            
            # Generate tickets for this batch
            for i in range(seat_count):
                ticket_code = generate_ticket_code()
                barcode = f"TICKET-{event_id}-{batch.id}-{i+1}"
                
                # Generate barcode image
                barcode_path = create_event_pass_barcode(
                    barcode,
                    event.event_name,
                    f"Ticket #{i+1}",
                    batch.batch_name
                )
                
                ticket = Ticket(
                    batch_id=batch.id,
                    ticket_code=ticket_code,
                    barcode=barcode,
                    price=price
                )
                db.session.add(ticket)
            
            db.session.commit()
            flash(f'Batch created successfully with {seat_count} tickets!', 'success')
            return redirect(url_for('tickets.list_tickets', event_id=event_id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating batch: {str(e)}', 'error')
    
    return render_template('tickets/create_batch.html', event=event)

@tickets_bp.route('/promotion/create/<int:event_id>', methods=['GET', 'POST'])
@login_required
def create_promotion(event_id):
    """Create a new promotion"""
    event = Event.query.get_or_404(event_id)
    
    # Check permission
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to create promotions', 'error')
        return redirect(url_for('dashboard.home'))
    
    if request.method == 'POST':
        try:
            promotion_name = request.form.get('promotion_name')
            promotion_type = request.form.get('promotion_type')
            value = request.form.get('value')
            quantity = int(request.form.get('quantity', 1))
            
            promotion = Promotion(
                event_id=event_id,
                promotion_name=promotion_name,
                promotion_type=promotion_type,
                value=value,
                quantity=quantity
            )
            db.session.add(promotion)
            db.session.commit()
            
            flash('Promotion created successfully!', 'success')
            return redirect(url_for('tickets.list_tickets', event_id=event_id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating promotion: {str(e)}', 'error')
    
    return render_template('tickets/create_promotion.html', event=event)

@tickets_bp.route('/scan/<int:ticket_id>', methods=['POST'])
@login_required
def scan_ticket(ticket_id):
    """Scan and validate a ticket"""
    try:
        ticket = Ticket.query.get_or_404(ticket_id)
        
        if ticket.status == 'used':
            return jsonify({
                'success': False,
                'message': 'Ticket already used',
                'scanned_at': ticket.scanned_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.scanned_at else None
            })
        
        if ticket.status == 'expired':
            return jsonify({
                'success': False,
                'message': 'Ticket has expired'
            })
        
        # Mark ticket as used
                try:
            ticket.status = 'used'
            ticket.scanned_by = current_user.username
            from datetime import datetime
            ticket.scanned_at = datetime.utcnow()
            
            db.session.commit()
                    except Exception as e:
                                    db.session.rollback()
                                    return jsonify({
                                                        'success': False,
                                                        'message': 'Error validating ticket'
                                                    })
            
        return jsonify({
            'success': True,
            'message': 'Ticket validated successfully',
            'ticket_code': ticket.ticket_code,
            'scanned_by': current_user.username
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error scanning ticket: {str(e)}'
        }), 500

@tickets_bp.route('/scan/by-code', methods=['POST'])
@login_required
def scan_by_code():
    """Scan ticket by barcode/QR code"""
    try:
        code = request.json.get('code')
        
        ticket = Ticket.query.filter(
            (Ticket.ticket_code == code) | (Ticket.barcode == code)
        ).first()
        
        if not ticket:
            return jsonify({
                'success': False,
                'message': 'Ticket not found'
            }), 404
        
        if ticket.status == 'used':
            return jsonify({
                'success': False,
                'message': 'Ticket already used',
                'scanned_at': ticket.scanned_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.scanned_at else None,
                'scanned_by': ticket.scanned_by
            })
        
        if ticket.status == 'expired':
            return jsonify({
                'success': False,
                'message': 'Ticket has expired'
            })
        
        # Mark ticket as used
        ticket.status = 'used'
        ticket.scanned_by = current_user.username
        from datetime import datetime
        ticket.scanned_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Ticket validated successfully',
            'ticket_code': ticket.ticket_code,
            'price': ticket.price,
            'scanned_by': current_user.username
        })

        except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@tickets_bp.route('/scanner')
@login_required
def scanner():
    """Ticket scanner page"""
    return render_template('tickets/scanner.html')
    
    
