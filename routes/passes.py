from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import Event, EventPass, PassType, EventAnalytics
from database import db
from utils.qr_generator import create_event_pass_qr, generate_pass_code
from utils.barcode_generator import create_event_pass_barcode
from utils.capacity import get_event_capacity_snapshot
import os
import shutil
from datetime import datetime, timedelta

bp = Blueprint('passes', __name__, url_prefix='/passes')

# Fixed system ticket types (not user-customizable)
FIXED_PASS_TYPES = {
    'VIP': {
        'description': 'VIP access pass',
        'access_level': 5,
        'color_code': '#d4af37',
    },
    'Judge': {
        'description': 'Judge access pass',
        'access_level': 4,
        'color_code': '#dc3545',
    },
    'Mentor': {
        'description': 'Mentor access pass',
        'access_level': 3,
        'color_code': '#17a2b8',
    },
    'Staff': {
        'description': 'Staff access pass',
        'access_level': 3,
        'color_code': '#6f42c1',
    },
    'Participant': {
        'description': 'Participant access pass',
        'access_level': 2,
        'color_code': '#007bff',
    },
    'Volunteer': {
        'description': 'Volunteer access pass',
        'access_level': 2,
        'color_code': '#20c997',
    },
    'Speaker': {
        'description': 'Speaker access pass',
        'access_level': 3,
        'color_code': '#fd7e14',
    },
    'Sponsor': {
        'description': 'Sponsor access pass',
        'access_level': 3,
        'color_code': '#28a745',
    },
}


def ensure_fixed_pass_types():
    """Create fixed pass types if they do not exist and return them ordered."""
    changed = False

    for type_name, meta in FIXED_PASS_TYPES.items():
        exists = PassType.query.filter_by(type_name=type_name).first()
        if exists:
            continue

        db.session.add(PassType(
            type_name=type_name,
            description=meta['description'],
            access_level=meta['access_level'],
            color_code=meta['color_code'],
        ))
        changed = True

    if changed:
        db.session.commit()

    return PassType.query.filter(
        PassType.type_name.in_(list(FIXED_PASS_TYPES.keys()))
    ).order_by(PassType.type_name.asc()).all()


# =========================
# Generate Pass Form (GET)
# =========================
@bp.route('/generate', methods=['GET'])
@login_required
def generate_form():
    if current_user.role == 'admin':
        events = Event.query.filter_by(status='active').all()
    else:
        events = Event.query.filter_by(
            organizer_id=current_user.id,
            status='active'
        ).all()

    pass_types = ensure_fixed_pass_types()
    return render_template(
        'passes/generate.html',
        events=events,
        pass_types=pass_types
    )


# =========================
# Generate Passes (POST)
# =========================
@bp.route('/generate', methods=['POST'])
@login_required
def generate_pass():
    try:
        event_id = int(request.form.get('event_id', '0'))
        quantity = int(request.form.get('quantity', 1))
    except ValueError:
        flash('Invalid event or quantity value', 'danger')
        return redirect(url_for('passes.generate_form'))

    if quantity < 1 or quantity > 100:
        flash('Quantity must be between 1 and 100', 'danger')
        return redirect(url_for('passes.generate_form'))

    pass_type_name = (request.form.get('pass_type') or '').strip()
    if pass_type_name not in FIXED_PASS_TYPES:
        flash('Invalid pass type selected. Custom pass types are disabled.', 'danger')
        return redirect(url_for('passes.generate_form'))

    participant_name = (request.form.get('participant_name') or 'Participant').strip()
    participant_email = (
        request.form.get('participant_email')
        or request.form.get('email')
        or ''
    ).strip()
    participant_phone = (
        request.form.get('participant_phone')
        or request.form.get('phone')
        or ''
    ).strip()

    event = Event.query.get_or_404(event_id)

    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to generate passes for this event.', 'danger')
        return redirect(url_for('dashboard.home'))

    ensure_fixed_pass_types()
    pass_type = PassType.query.filter_by(type_name=pass_type_name).first()
    if not pass_type:
        flash('Pass type configuration is missing. Please try again.', 'danger')
        return redirect(url_for('passes.generate_form'))

    pass_type_id = pass_type.id

    capacity = get_event_capacity_snapshot(event)
    if quantity > capacity['remaining']:
        flash(
            (
                f'Capacity exceeded. This event allows {capacity["total_capacity"]} total attendees, '
                f'and {capacity["allocated_total"]} are already allocated '
                f'({capacity["pass_count"]} passes + {capacity["ticket_count"]} tickets). '
                f'Remaining capacity: {max(capacity["remaining"], 0)}.'
            ),
            'danger'
        )
        return redirect(url_for('passes.generate_form'))

    generated_passes = []

    try:
        for i in range(quantity):
            # Generate unique pass code
            pass_code = generate_pass_code(
                event_id,
                pass_type.type_name,
                i + 1
            )

            display_name = (
                f"{participant_name} {i + 1}"
                if quantity > 1 else participant_name
            )

            # ✅ Generate QR code that contains ONLY pass_code
            qr_path, qr_payload = create_event_pass_qr(
                pass_code,
                event.event_name,
                display_name,
                pass_type.type_name
            )

            # ✅ Store qr_payload into encrypted_data for backward compatibility
            encrypted_data = qr_payload

            # Generate barcode (barcode already uses pass_code)
            barcode_path = create_event_pass_barcode(
                pass_code,
                event.event_name,
                display_name,
                pass_type.type_name
            )

            expiry_days = int(os.getenv('PASS_EXPIRY_DAYS', 30))
            expires_at = datetime.utcnow() + timedelta(days=expiry_days)

            new_pass = EventPass(
                event_id=event_id,
                pass_type_id=pass_type_id,
                pass_code=pass_code,
                encrypted_data=encrypted_data,   # now equals pass_code
                participant_name=display_name,
                participant_email=participant_email,
                participant_phone=participant_phone,
                qr_code_path=qr_path,
                barcode_path=barcode_path,
                expires_at=expires_at
            )

            db.session.add(new_pass)
            generated_passes.append(new_pass)

        db.session.commit()

        # -------------------------
        # Update Analytics
        # -------------------------
        analytics = EventAnalytics.query.filter_by(
            event_id=event_id
        ).first()

        if not analytics:
            analytics = EventAnalytics(event_id=event_id)

        # Initialize None values to 0 to prevent NoneType errors
        analytics.total_passes_generated = analytics.total_passes_generated or 0
        db.session.add(analytics)

        analytics.total_passes_generated += quantity
        db.session.commit()

        flash(
            f'Successfully generated {quantity} pass(es)!',
            'success'
        )
        return redirect(
            url_for('passes.view_passes', event_id=event_id)
        )

    except Exception as e:
        db.session.rollback()
        flash(f'Error generating passes: {str(e)}', 'danger')
        return redirect(url_for('passes.generate_form'))


# =========================
# View Passes
# =========================
@bp.route('/view/<int:event_id>')
@login_required
def view_passes(event_id):
    event = Event.query.get_or_404(event_id)

    # Security check: Only organizer can view their event passes
    if event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to view these passes', 'danger')
        return redirect(url_for('dashboard.home'))

    passes = EventPass.query.filter_by(event_id=event_id).all()

    static_root = current_app.static_folder
    legacy_static_root = os.path.abspath(os.path.join(current_app.root_path, '..', 'static'))

    def resolve_asset(path_value):
        if not path_value:
            return None, False

        normalized = str(path_value).replace('\\', '/')
        if normalized.startswith('static/'):
            public_path = normalized[7:]
            absolute_path = os.path.join(static_root, public_path.replace('/', os.sep))
        elif os.path.isabs(path_value):
            absolute_path = path_value
            try:
                rel = os.path.relpath(os.path.abspath(path_value), os.path.abspath(static_root))
                public_path = rel.replace('\\', '/') if not rel.startswith('..') else None
            except ValueError:
                public_path = None
        else:
            public_path = normalized.lstrip('/')
            absolute_path = os.path.join(static_root, public_path.replace('/', os.sep))

        exists = os.path.exists(absolute_path)

        # Backfill legacy files generated outside project static directory.
        if not exists and public_path:
            legacy_absolute = os.path.join(legacy_static_root, public_path.replace('/', os.sep))
            if os.path.exists(legacy_absolute):
                os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
                try:
                    shutil.copy2(legacy_absolute, absolute_path)
                    exists = True
                except OSError:
                    exists = False

        return public_path, exists

    for pass_obj in passes:
        qr_public, qr_exists = resolve_asset(pass_obj.qr_code_path)
        barcode_public, barcode_exists = resolve_asset(pass_obj.barcode_path)

        pass_obj.qr_public_path = qr_public
        pass_obj.qr_exists = qr_exists
        pass_obj.barcode_public_path = barcode_public
        pass_obj.barcode_exists = barcode_exists

    return render_template(
        'passes/view.html',
        event=event,
        passes=passes
    )


# =========================
# Download Pass
# =========================
@bp.route('/download/<int:pass_id>')
@login_required
def download_pass(pass_id):
    pass_obj = EventPass.query.get_or_404(pass_id)

    # Security check: Only event organizer can download passes
    if pass_obj.event.organizer_id != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to download this pass', 'danger')
        return redirect(url_for('dashboard.home'))

    return render_template(
        'passes/download.html',
        pass_obj=pass_obj
    )
