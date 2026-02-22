from database import db
from models import Event, Gate, EventScannerAssignment


def get_scannable_active_events(user, event_wide_only=False):
    """
    Return active events this user can scan.
    - admin: all active events
    - organizer: own active events + assigned active events
    - security: assigned active events only
    """
    if user.role == 'admin':
        return Event.query.filter_by(status='active').order_by(Event.event_date.asc(), Event.event_time.asc()).all()

    rows_query = EventScannerAssignment.query.filter_by(
        scanner_user_id=user.id,
        is_active=True
    )
    if event_wide_only:
        rows_query = rows_query.filter(EventScannerAssignment.gate_id.is_(None))
    rows = rows_query.all()
    assigned_event_ids = {row.event_id for row in rows}

    events_by_id = {}
    if user.role == 'organizer':
        owned = Event.query.filter_by(
            organizer_id=user.id,
            status='active'
        ).order_by(Event.event_date.asc(), Event.event_time.asc()).all()
        for event in owned:
            events_by_id[event.id] = event

    if assigned_event_ids:
        assigned_events = Event.query.filter(
            Event.id.in_(list(assigned_event_ids)),
            Event.status == 'active'
        ).all()
        for event in assigned_events:
            events_by_id[event.id] = event

    return sorted(
        events_by_id.values(),
        key=lambda event: (
            event.event_date or '',
            event.event_time or '',
            event.id
        )
    )


def user_can_scan_event(user, event):
    if not event:
        return False

    if user.role == 'admin':
        return True

    if event.organizer_id == user.id:
        return True

    return EventScannerAssignment.query.filter_by(
        scanner_user_id=user.id,
        event_id=event.id,
        is_active=True
    ).first() is not None


def user_gate_scope_for_event(user, event_id):
    """
    Return gate scope:
    - None => full event gate access
    - empty set => no access
    - set(gate_ids) => access to those gates only
    """
    if user.role == 'admin':
        return None

    event = Event.query.get(event_id)
    if event and event.organizer_id == user.id:
        return None

    rows = EventScannerAssignment.query.filter_by(
        scanner_user_id=user.id,
        event_id=event_id,
        is_active=True
    ).all()

    if not rows:
        return set()

    if any(row.gate_id is None for row in rows):
        return None

    return {row.gate_id for row in rows if row.gate_id is not None}


def user_can_scan_gate(user, gate):
    if not gate:
        return False

    scope = user_gate_scope_for_event(user, gate.event_id)
    if scope is None:
        return True
    if not scope:
        return False
    return gate.id in scope


def user_has_event_wide_scan_access(user, event):
    if not event:
        return False

    scope = user_gate_scope_for_event(user, event.id)
    return scope is None


def get_scannable_active_gates(user, event_id=None):
    """
    Return active gates user can scan.
    """
    base_query = Gate.query.filter_by(is_active=True)
    if event_id:
        base_query = base_query.filter_by(event_id=event_id)

    if user.role == 'admin':
        return base_query.order_by(Gate.event_id.asc(), Gate.gate_name.asc()).all()

    allowed_gate_ids = set()

    if user.role == 'organizer':
        owned_gate_ids_query = (
            db.session.query(Gate.id)
            .join(Event, Gate.event_id == Event.id)
            .filter(
                Gate.is_active == True,  # noqa: E712
                Event.organizer_id == user.id
            )
        )
        if event_id:
            owned_gate_ids_query = owned_gate_ids_query.filter(Gate.event_id == event_id)
        allowed_gate_ids.update(gate_id for gate_id, in owned_gate_ids_query.all())

    rows_query = EventScannerAssignment.query.filter_by(
        scanner_user_id=user.id,
        is_active=True
    )
    if event_id:
        rows_query = rows_query.filter_by(event_id=event_id)
    rows = rows_query.all()

    assigned_gate_ids = {row.gate_id for row in rows if row.gate_id is not None}
    allowed_gate_ids.update(assigned_gate_ids)

    event_wide_ids = {row.event_id for row in rows if row.gate_id is None}
    if event_wide_ids:
        event_wide_gate_ids_query = (
            db.session.query(Gate.id)
            .filter(
                Gate.is_active == True,  # noqa: E712
                Gate.event_id.in_(list(event_wide_ids))
            )
        )
        if event_id:
            event_wide_gate_ids_query = event_wide_gate_ids_query.filter(Gate.event_id == event_id)
        allowed_gate_ids.update(gate_id for gate_id, in event_wide_gate_ids_query.all())

    if not allowed_gate_ids:
        return []

    return (
        base_query
        .filter(Gate.id.in_(list(allowed_gate_ids)))
        .order_by(Gate.event_id.asc(), Gate.gate_name.asc())
        .all()
    )
