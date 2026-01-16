from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from database import db
from models import EventPass, Event, ValidationLog
from cryptography.fernet import Fernet
from datetime import datetime
import os
import json

validation_bp = Blueprint('validation', __name__)

# Load encryption key
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'default-dev-encryption-key-change-this-32char').encode()
cipher = Fernet(ENCRYPTION_KEY)

@validation_bp.route('/validate', methods=['GET', 'POST'])
@login_required
def validate_pass():
    """Display validation scanner page and handle validation requests"""
    if request.method == 'GET':
        return render_template('validation/scanner.html')
    
    # Handle POST request for validation
    try:
        data = request.get_json()
        scanned_code = data.get('code')
        
        if not scanned_code:
            return jsonify({
                'success': False,
                'message': 'No code provided'
            }), 400
        
        # Try to find pass by pass_code first (for manual entry)
        pass_obj = EventPass.query.filter_by(pass_code=scanned_code).first()
        
        # If not found, try to decrypt as QR/encrypted data
        if not pass_obj:
            try:
                decrypted_data = cipher.decrypt(scanned_code.encode()).decode()
                pass_data = json.loads(decrypted_data)
                pass_id = pass_data.get('pass_id')
                pass_obj = EventPass.query.get(pass_id)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': 'Invalid or corrupted code',
                    'error': str(e)
                }), 400
        
        if not pass_obj:
            return jsonify({
                'success': False,
                'message': 'Pass not found in system'
            }), 404
        
        # Check if pass is already validated
        if pass_obj.is_validated:
            return jsonify({
                'success': False,
                'message': 'Pass already validated',
                'validated_at': pass_obj.validation_logs[0].validation_time.strftime('%Y-%m-%d %H:%M:%S') if pass_obj.validation_logs else 'N/A',
                'pass_info': {
                    'participant_name': pass_obj.participant_name,
                    'pass_type': pass_obj.pass_type.type_name if pass_obj.pass_type else 'Unknown',
                    'event': pass_obj.event.event_name
                }
            }), 400
        
        # Validate the pass
        pass_obj.is_validated = True
        pass_obj.validation_count += 1
        
        # Log the validation
        validation_log = ValidationLog(
            pass_id=pass_obj.id,
            validator_id=current_user.id,
            validation_time=datetime.utcnow(),
            validation_status='success',
            validation_message='Pass validated successfully'
        )
        
        db.session.add(validation_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Pass validated successfully!',
            'pass_info': {
                'id': pass_obj.id,
                'participant_name': pass_obj.participant_name,
                'email': pass_obj.participant_email,
                'phone': pass_obj.participant_phone,
                'pass_type': pass_obj.pass_type.type_name if pass_obj.pass_type else 'Unknown',
                'event': pass_obj.event.event_name,
                'event_date': pass_obj.event.event_date.strftime('%B %d, %Y'),
                'validated_at': validation_log.validation_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Validation error occurred',
            'error': str(e)
        }), 500

@validation_bp.route('/validate/manual', methods=['POST'])
@login_required
def manual_validate():
    """Manually validate a pass by ID or participant info"""
    try:
        data = request.form
        pass_id = data.get('pass_id')
        participant_name = data.get('participant_name')
        
        # Find pass by ID or name
        if pass_id:
            pass_obj = EventPass.query.get(pass_id)
        elif participant_name:
            pass_obj = EventPass.query.filter_by(participant_name=participant_name).first()
        else:
            return jsonify({
                'success': False,
                'message': 'Please provide pass ID or participant name'
            }), 400
        
        if not pass_obj:
            return jsonify({
                'success': False,
                'message': 'Pass not found'
            }), 404
        
        if pass_obj.is_validated:
            return jsonify({
                'success': False,
                'message': 'Pass already validated'
            }), 400
        
        # Validate pass
        pass_obj.is_validated = True
        pass_obj.validation_count += 1
        
        # Log validation
        validation_log = ValidationLog(
            pass_id=pass_obj.id,
            validator_id=current_user.id,
            validation_time=datetime.utcnow(),
            validation_status='success',
            validation_message='Manual validation'
        )
        
        db.session.add(validation_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Pass validated successfully',
            'pass_info': {
                'participant_name': pass_obj.participant_name,
                'pass_type': pass_obj.pass_type.type_name if pass_obj.pass_type else 'Unknown',
                'event': pass_obj.event.event_name
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@validation_bp.route('/validation/history', methods=['GET'])
@login_required
def validation_history():
    """Get validation history for an event"""
    event_id = request.args.get('event_id')
    
    if event_id:
        validations = ValidationLog.query.join(EventPass).filter(
            EventPass.event_id == event_id
        ).order_by(ValidationLog.validation_time.desc()).all()
    else:
        validations = ValidationLog.query.order_by(
            ValidationLog.validation_time.desc()
        ).limit(50).all()
    
    history = []
    for log in validations:
        history.append({
            'id': log.id,
            'pass_id': log.pass_id,
            'participant': log.pass_.participant_name,
            'event': log.pass_.event.event_name,
            'validated_at': log.validation_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': log.validation_status
        })
    
    return jsonify({
        'success': True,
        'validations': history
    }), 200

@validation_bp.route('/validation/stats', methods=['GET'])
@login_required
def validation_stats():
    """Get validation statistics"""
    event_id = request.args.get('event_id')
    
    if event_id:
        total_passes = EventPass.query.filter_by(event_id=event_id).count()
        validated_passes = EventPass.query.filter_by(
            event_id=event_id, 
            is_validated=True
        ).count()
    else:
        total_passes = EventPass.query.count()
        validated_passes = EventPass.query.filter_by(is_validated=True).count()
    
    pending_passes = total_passes - validated_passes
    validation_rate = (validated_passes / total_passes * 100) if total_passes > 0 else 0
    
    return jsonify({
        'success': True,
        'stats': {
            'total_passes': total_passes,
            'validated_passes': validated_passes,
            'pending_passes': pending_passes,
            'validation_rate': round(validation_rate, 2)
        }
    }), 200
