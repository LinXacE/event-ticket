from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from database import db
from models import Event, TicketType
from utils.decorators import organizer_or_admin

ticket_types_bp = Blueprint('ticket_types', __name__, url_prefix='/ticket-types')

@ticket_types_bp.route('/event/<int:event_id>', methods=['GET'])
@login_required
def manage_ticket_types(event_id):
    """Manage ticket types for a specific event."""
    event = Event.query.get_or_404(event_id)
    
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('Permission denied.', 'error')
        return redirect(url_for('events.list_events'))
    
    ticket_types = TicketType.query.filter_by(event_id=event_id).all()
    return render_template('ticket_types/manage.html', event=event, ticket_types=ticket_types)

@ticket_types_bp.route('/event/<int:event_id>/create', methods=['POST'])
@login_required
def create_ticket_type(event_id):
    """Create a new ticket type for an event."""
    event = Event.query.get_or_404(event_id)
    
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Permission denied'}), 403
    
    type_name = request.form.get('type_name', '').strip()
    if not type_name:
        return jsonify({'error': 'Type name is required'}), 400
    
    ticket_type = TicketType(
        event_id=event_id,
        type_name=type_name,
        description=request.form.get('description', ''),
        max_quantity=int(request.form.get('max_quantity', 0)),
        price=float(request.form.get('price', 0.0)),
        color_code=request.form.get('color_code', '#007bff'),
        access_level=int(request.form.get('access_level', 1))
    )
    
    db.session.add(ticket_type)
    db.session.commit()
    
    flash(f'Ticket type "{type_name}" created successfully.', 'success')
    return redirect(url_for('ticket_types.manage_ticket_types', event_id=event_id))

@ticket_types_bp.route('/<int:type_id>/update', methods=['POST'])
@login_required
def update_ticket_type(type_id):
    """Update a ticket type."""
    ticket_type = TicketType.query.get_or_404(type_id)
    event = ticket_type.event
    
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Permission denied'}), 403
    
    ticket_type.type_name = request.form.get('type_name', ticket_type.type_name)
    ticket_type.description = request.form.get('description', ticket_type.description)
    ticket_type.max_quantity = int(request.form.get('max_quantity', ticket_type.max_quantity))
    ticket_type.price = float(request.form.get('price', ticket_type.price))
    ticket_type.color_code = request.form.get('color_code', ticket_type.color_code)
    
    db.session.commit()
    flash('Ticket type updated successfully.', 'success')
    return redirect(url_for('ticket_types.manage_ticket_types', event_id=event.id))

@ticket_types_bp.route('/<int:type_id>/delete', methods=['POST'])
@login_required
def delete_ticket_type(type_id):
    """Delete a ticket type."""
    ticket_type = TicketType.query.get_or_404(type_id)
    event_id = ticket_type.event_id
    event = ticket_type.event
    
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': 'Permission denied'}), 403
    
    db.session.delete(ticket_type)
    db.session.commit()
    flash('Ticket type deleted successfully.', 'success')
    return redirect(url_for('ticket_types.manage_ticket_types', event_id=event_id))

@ticket_types_bp.route('/event/<int:event_id>/api', methods=['GET'])
def get_event_ticket_types(event_id):
    """Get ticket types for an event as JSON (for frontend)."""
    ticket_types = TicketType.query.filter_by(event_id=event_id).all()
    return jsonify([{
        'id': t.id,
        'type_name': t.type_name,
        'max_quantity': t.max_quantity,
        'quantity_generated': t.quantity_generated,
        'remaining_quantity': t.remaining_quantity,
        'price': t.price,
        'color_code': t.color_code,
        'access_level': t.access_level
    } for t in ticket_types])
