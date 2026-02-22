from database import db
from models import Event, EventPass, Ticket, TicketBatch


def _resolve_event_id(event_or_id):
    if isinstance(event_or_id, Event):
        return event_or_id.id
    return int(event_or_id)


def get_event_pass_count(event_or_id):
    event_id = _resolve_event_id(event_or_id)
    return EventPass.query.filter_by(event_id=event_id).count()


def get_event_ticket_count(event_or_id):
    event_id = _resolve_event_id(event_or_id)
    total = (
        db.session.query(db.func.count(Ticket.id))
        .join(TicketBatch, Ticket.batch_id == TicketBatch.id)
        .filter(TicketBatch.event_id == event_id)
        .scalar()
    )
    return int(total or 0)


def get_event_allocated_total(event_or_id):
    return get_event_pass_count(event_or_id) + get_event_ticket_count(event_or_id)


def get_event_capacity_snapshot(event):
    event_id = _resolve_event_id(event)

    if isinstance(event, Event):
        total_capacity = int(event.total_capacity or 0)
    else:
        total_capacity = int(
            Event.query.with_entities(Event.total_capacity)
            .filter(Event.id == event_id)
            .scalar() or 0
        )

    pass_count = get_event_pass_count(event_id)
    ticket_count = get_event_ticket_count(event_id)
    allocated_total = pass_count + ticket_count

    return {
        'total_capacity': total_capacity,
        'pass_count': pass_count,
        'ticket_count': ticket_count,
        'allocated_total': allocated_total,
        'remaining': total_capacity - allocated_total,
    }

