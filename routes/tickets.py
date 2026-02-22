from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import Event, TicketBatch, Ticket, Promotion
from database import db
from utils.barcode_generator import create_event_pass_barcode
from utils.capacity import get_event_capacity_snapshot
from utils.scanner_access import (
    get_scannable_active_events,
    user_can_scan_event,
    user_has_event_wide_scan_access
)
import secrets
import string
import os
import shutil
from datetime import datetime


tickets_bp = Blueprint('tickets', __name__, url_prefix='/tickets')


def generate_ticket_code(length=8):
    """Generate a random ticket code"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def _event_for_ticket(ticket: Ticket):
    if not ticket or not ticket.batch:
        return None
    return Event.query.get(ticket.batch.event_id)


def _can_manage_event(event: Event):
    if not event:
        return False
    return user_can_scan_event(current_user, event)


@tickets_bp.route('/event/<int:event_id>')
@login_required
def list_tickets(event_id):
    """List all tickets for an event"""
    event = Event.query.get_or_404(event_id)

    # Permission check
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to view these tickets', 'error')
        return redirect(url_for('dashboard.home'))

    batches = TicketBatch.query.filter_by(event_id=event_id).all()
    tickets = []
    static_root = current_app.static_folder
    legacy_static_root = os.path.abspath(os.path.join(current_app.root_path, '..', 'static'))
    for batch in batches:
        for ticket in batch.tickets:
            local_path = f"barcodes/pass_{ticket.barcode}.png"
            absolute_path = os.path.join(static_root, local_path.replace('/', os.sep))
            exists = os.path.exists(absolute_path)

            if not exists:
                legacy_absolute = os.path.join(legacy_static_root, local_path.replace('/', os.sep))
                if os.path.exists(legacy_absolute):
                    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
                    try:
                        shutil.copy2(legacy_absolute, absolute_path)
                        exists = True
                    except OSError:
                        exists = False

            ticket.local_barcode_path = local_path if exists else None
            tickets.append(ticket)

    return render_template('tickets/list.html', event=event, batches=batches, tickets=tickets)


@tickets_bp.route('/batch/create/<int:event_id>', methods=['GET', 'POST'])
@login_required
def create_batch(event_id):
    """Create a new ticket batch"""
    event = Event.query.get_or_404(event_id)

    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to create batches', 'error')
        return redirect(url_for('dashboard.home'))

    if request.method == 'POST':
        try:
            batch_name = request.form.get('batch_name')
            batch_type = request.form.get('batch_type', 'normal')
            seat_count = int(request.form.get('seat_count', 0))
            price = float(request.form.get('price', 0.0))

            if not (batch_name or '').strip():
                flash('Batch name is required', 'error')
                return redirect(url_for('tickets.create_batch', event_id=event_id))

            if seat_count < 1:
                flash('Seat count must be at least 1', 'error')
                return redirect(url_for('tickets.create_batch', event_id=event_id))

            capacity = get_event_capacity_snapshot(event)
            if seat_count > capacity['remaining']:
                flash(
                    (
                        f'Capacity exceeded. This event allows {capacity["total_capacity"]} total attendees, '
                        f'and {capacity["allocated_total"]} are already allocated '
                        f'({capacity["pass_count"]} passes + {capacity["ticket_count"]} tickets). '
                        f'Remaining capacity: {max(capacity["remaining"], 0)}.'
                    ),
                    'error'
                )
                return redirect(url_for('tickets.create_batch', event_id=event_id))

            batch = TicketBatch(
                event_id=event_id,
                batch_name=batch_name,
                batch_type=batch_type,
                seat_count=seat_count
            )
            db.session.add(batch)
            db.session.flush()  # get batch.id

            for i in range(seat_count):
                ticket_code = generate_ticket_code()
                barcode = f"TICKET-{event_id}-{batch.id}-{i + 1}"

                # generate barcode image (side effect)
                create_event_pass_barcode(
                    barcode,
                    event.event_name,
                    f"Ticket #{i + 1}",
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
    """Scan and validate a ticket by ID"""
    try:
        ticket = Ticket.query.get_or_404(ticket_id)
        event = _event_for_ticket(ticket)
        if not _can_manage_event(event):
            return jsonify({'success': False, 'message': 'Not authorized for this event'}), 403

        if not user_has_event_wide_scan_access(current_user, event):
            return jsonify({
                'success': False,
                'message': 'Your scanner assignment is gate-specific. Use Validate Pass page and choose your assigned gate.'
            }), 403

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

        ticket.status = 'used'
        ticket.scanned_by = current_user.username
        ticket.scanned_at = datetime.utcnow()

        db.session.commit()

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
    """Scan ticket by ticket code or barcode"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'message': 'Invalid JSON request'}), 400

        code = (request.json.get('code') or '').strip()
        code = code.replace('\u200b', '').replace('\ufeff', '')
        if not code:
            return jsonify({'success': False, 'message': 'Code is required'}), 400

        upper_code = code.upper()
        ticket = Ticket.query.filter(
            (Ticket.ticket_code == code) |
            (Ticket.ticket_code == upper_code) |
            (Ticket.barcode == code) |
            (Ticket.barcode == upper_code)
        ).first()

        if not ticket:
            return jsonify({'success': False, 'message': 'Ticket not found'}), 404

        event = _event_for_ticket(ticket)
        selected_event_id = request.json.get('event_id')
        if selected_event_id is not None and selected_event_id != '':
            try:
                selected_event_id = int(selected_event_id)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'event_id must be a valid integer'}), 400

            if event and event.id != selected_event_id:
                selected_event = Event.query.get(selected_event_id)
                return jsonify({
                    'success': False,
                    'message': (
                        f'Wrong event ticket. This ticket belongs to "{event.event_name}" '
                        f'but scanner is set to "{selected_event.event_name if selected_event else f"Event #{selected_event_id}"}".'
                    ),
                    'event_mismatch': True,
                    'ticket_event': event.event_name,
                    'selected_event': selected_event.event_name if selected_event else None
                }), 403

        if not _can_manage_event(event):
            return jsonify({'success': False, 'message': 'Not authorized for this event'}), 403

        if not user_has_event_wide_scan_access(current_user, event):
            return jsonify({
                'success': False,
                'message': 'Your scanner assignment is gate-specific. Use Validate Pass page and choose your assigned gate.'
            }), 403

        if ticket.status == 'used':
            return jsonify({
                'success': False,
                'message': 'Ticket already used',
                'scanned_at': ticket.scanned_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.scanned_at else None,
                'scanned_by': ticket.scanned_by
            })

        if ticket.status == 'expired':
            return jsonify({'success': False, 'message': 'Ticket has expired'})

        ticket.status = 'used'
        ticket.scanned_by = current_user.username
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
    events = get_scannable_active_events(current_user, event_wide_only=True)

    return render_template('tickets/scanner.html', events=events)
