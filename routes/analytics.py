from flask import Blueprint, render_template, jsonify
from database import db
from models import Event, EventPass, EventAnalytics
from flask_login import login_required

bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@bp.route('/')
@login_required
def index():
    """Analytics dashboard page"""
    return render_template('analytics/index.html')

@bp.route('/data/<int:event_id>')
@login_required
def event_data(event_id):
    """Get analytics data for a specific event"""
    analytics = EventAnalytics.query.filter_by(event_id=event_id).first()
    
    if analytics:
        return jsonify({
            'success': True,
            'data': {
                'total_passes': analytics.total_passes_generated,
                'validated_passes': analytics.total_passes_validated,
                'judges': analytics.judges_count,
                'mentors': analytics.mentors_count,
                'participants': analytics.participants_count,
                'volunteers': analytics.volunteers_count,
                'guests': analytics.guests_count
            }
        }), 200
    
    return jsonify({
        'success': False,
        'message': 'No analytics data found for this event'
    }), 404
