from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Event, EventPass, PassType, EventAnalytics
from database import db
from utils.qr_generator import create_event_pass_qr, generate_pass_code
from utils.barcode_generator import create_event_pass_barcode
import os
from datetime import datetime, timedelta

bp = Blueprint('passes', __name__, url_prefix='/passes')

@bp.route('/generate', methods=['GET'])
@login_required
def generate_form():
    events = Event.query.filter_by(organizer_id=current_user.id, status='active').all()
    pass_types = PassType.query.all()
    return render_template('passes/generate.html', events=events, pass_types=pass_types)

@bp.route('/generate', methods=['POST'])
@login_required
def generate_pass():
    event_id = request.form.get('event_id')
    pass_type_name = request.form.get('pass_type')  # Now getting name instead of ID
    
    event = Event.query.get_or_404(event_id)
    
    # Get or create pass type
    pass_type = PassType.query.filter_by(type_name=pass_type_name).first()
    if not pass_type:
        # Create new custom pass type
        pass_type = PassType(
            type_name=pass_type_name,
            description=f'Custom pass type: {pass_type_name}',
            access_level=3,  # Default access level
            color_code='#007bff'  # Default color
        )
        db.session.add(pass_type)
        db.session.flush()  # Get the IDt_or_404(pass_type_id)
    
    secret_key = os.getenv('ENCRYPTION_KEY', 'default-secret-key')
    generated_passes = []
    
    try:
        for i in range(quantity):
            # Generate unique pass code
            pass_code = generate_pass_code(event_id, pass_type.type_name, i+1)
            
            # Prepare pass data
            pass_data = {
                'event_id': event_id,
                'participant_id': i+1,
                'pass_type_id': pass_type_id
            }
            
            # Generate QR code
            qr_path, encrypted_data = create_event_pass_qr(
                pass_data, 
                pass_code, 
                event.event_name,
                f"{participant_name} {i+1}" if quantity > 1 else participant_name,
                pass_type.type_name,
                secret_key
            )
            
            # Generate Barcode  
            barcode_path = create_event_pass_barcode(
                pass_code,
                event.event_name,
                f"{participant_name} {i+1}" if quantity > 1 else participant_name,
                pass_type.type_name
            )
            
            # Calculate expiry
            expiry_days = int(os.getenv('PASS_EXPIRY_DAYS', 30))
            expires_at = datetime.utcnow() + timedelta(days=expiry_days)
            
            # Create pass record
            new_pass = EventPass(
                event_id=event_id,
                pass_type_id=pass_type_id,
                pass_code=pass_code,
                encrypted_data=encrypted_data,
                participant_name=f"{participant_name} {i+1}" if quantity > 1 else participant_name,
                participant_email=participant_email,
                participant_phone=participant_phone,
                qr_code_path=qr_path,
                barcode_path=barcode_path,
                expires_at=expires_at
            )
            
            db.session.add(new_pass)
            generated_passes.append(new_pass)
        
        db.session.commit()
        
        # Update analytics
        analytics = EventAnalytics.query.filter_by(event_id=event_id).first()
        if not analytics:
            analytics = EventAnalytics(event_id=event_id)
            db.session.add(analytics)
        
        analytics.total_passes_generated += quantity
        
        # Update pass type counts
        if pass_type.type_name == 'Judge':
            analytics.judges_count += quantity
        elif pass_type.type_name == 'Mentor':
            analytics.mentors_count += quantity
        elif pass_type.type_name == 'Participant':
            analytics.participants_count += quantity
        elif pass_type.type_name == 'Volunteer':
            analytics.volunteers_count += quantity
        else:
            analytics.guests_count += quantity
        
        db.session.commit()
        
        flash(f'Successfully generated {quantity} pass(es)!', 'success')
        return redirect(url_for('passes.view_passes', event_id=event_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error generating passes: {str(e)}', 'danger')
        return redirect(url_for('passes.generate_form'))

@bp.route('/view/<int:event_id>')
@login_required
def view_passes(event_id):
    event = Event.query.get_or_404(event_id)
    passes = EventPass.query.filter_by(event_id=event_id).all()
    return render_template('passes/view.html', event=event, passes=passes)

@bp.route('/download/<int:pass_id>')
@login_required
def download_pass(pass_id):
    pass_obj = EventPass.query.get_or_404(pass_id)
    return render_template('passes/download.html', pass_obj=pass_obj)
