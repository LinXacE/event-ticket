from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from database import db
from models import (
    Event, EventPass, ValidationLog, Ticket,
    Gate, GateAccessRule, GateValidationLog, TicketGateValidationLog
)
from datetime import datetime
import os
import json
from urllib.parse import urlparse, parse_qs, unquote
from cryptography.fernet import Fernet, InvalidToken
from utils.scanner_access import get_scannable_active_events, user_can_scan_gate

validation_bp = Blueprint('validation', __name__)

# OPTIONAL legacy decrypt support (for older QR codes)
def _load_fernet():
    key = os.getenv("ENCRYPTION_KEY", "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode())
    except Exception:
        return None

cipher = _load_fernet()


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def _normalize_scanned_code(raw_code: str) -> str:
    """Normalize scanner/manual input to improve match reliability."""
    code = (raw_code or "").strip()
    # Remove invisible characters that appear from copy/paste/scanner payloads
    code = code.replace('\u200b', '').replace('\ufeff', '')

    # Remove wrapping quotes that sometimes come from clipboard payloads
    if len(code) >= 2 and code[0] == code[-1] and code[0] in ("'", '"'):
        code = code[1:-1].strip()

    # Decode URL-encoded payload if present
    code = unquote(code)

    # If scanner returns a URL, try extracting known code params
    if code.lower().startswith(('http://', 'https://')):
        parsed = urlparse(code)
        params = parse_qs(parsed.query or '')
        for key in ('pass_code', 'code', 'pass', 'token', 'ticket'):
            value = params.get(key, [None])[0]
            if value:
                code = value.strip()
                break
        else:
            tail = (parsed.path or '').rstrip('/').rsplit('/', 1)[-1].strip()
            if tail:
                code = tail

    # Normalize accidental internal whitespace from manual entry
    code = ''.join(code.split())
    return code


def _find_ticket_hint(scanned_code: str):
    """Return ticket + event context if code belongs to ticket module."""
    upper_code = scanned_code.upper()
    ticket = Ticket.query.filter(
        (Ticket.ticket_code == scanned_code) |
        (Ticket.ticket_code == upper_code) |
        (Ticket.barcode == scanned_code) |
        (Ticket.barcode == upper_code)
    ).first()

    if not ticket:
        return None

    event_name = 'Unknown event'
    event_id = None
    if ticket.batch:
        event_id = ticket.batch.event_id
        event_obj = Event.query.get(event_id)
        if event_obj:
            event_name = event_obj.event_name

    return {
        "ticket_code": ticket.ticket_code,
        "barcode": ticket.barcode,
        "event_id": event_id,
        "event_name": event_name,
    }


def _resolve_ticket(scanned_code: str):
    upper_code = scanned_code.upper()
    return Ticket.query.filter(
        (Ticket.ticket_code == scanned_code) |
        (Ticket.ticket_code == upper_code) |
        (Ticket.barcode == scanned_code) |
        (Ticket.barcode == upper_code)
    ).first()


def _ticket_event(ticket_obj: Ticket):
    if not ticket_obj or not ticket_obj.batch:
        return None
    return Event.query.get(ticket_obj.batch.event_id)

def _resolve_pass(scanned_code: str):
    """
    New QR payload: pass_code only.
    Also supports legacy encrypted QR payloads if cipher exists.
    """
    upper_code = scanned_code.upper()

    # 1) direct pass_code lookup (new best practice)
    p = EventPass.query.filter_by(pass_code=scanned_code).first()
    if p:
        return p

    # 2) case-insensitive fallback for manual input
    if upper_code != scanned_code:
        p = EventPass.query.filter_by(pass_code=upper_code).first()
        if p:
            return p

    # 3) legacy: code was stored in encrypted_data column
    p = EventPass.query.filter_by(encrypted_data=scanned_code).first()
    if p:
        return p

    # 4) legacy: plain JSON payload from old QR generation
    try:
        payload = json.loads(scanned_code)
        if payload.get("pass_code"):
            code = str(payload["pass_code"]).strip()
            p = EventPass.query.filter_by(pass_code=code).first()
            if p:
                return p
        if payload.get("pass_id"):
            return EventPass.query.get(payload["pass_id"])
    except (ValueError, TypeError, json.JSONDecodeError):
        pass

    # 5) legacy encrypted decrypt support
    if cipher is None:
        return None

    try:
        decrypted = cipher.decrypt(scanned_code.encode()).decode()
        payload = json.loads(decrypted)
    except (InvalidToken, ValueError, json.JSONDecodeError):
        return None

    # allow pass_code or pass_id in legacy payload
    if payload.get("pass_code"):
        return EventPass.query.filter_by(pass_code=payload["pass_code"]).first()
    if payload.get("pass_id"):
        return EventPass.query.get(payload["pass_id"])

    return None


def _create_validation_log(pass_obj, status: str, message: str):
    log = ValidationLog(
        pass_id=pass_obj.id,
        validator_id=current_user.id,
        validation_time=datetime.utcnow(),
        validation_status=status,
        validation_message=message,
        ip_address=_client_ip(),
    )
    db.session.add(log)
    db.session.flush()  # ensures log.id exists
    return log


def _create_gate_log(validation_log_id: int, gate_id: int, granted: bool, message: str):
    gate_log = GateValidationLog(
        validation_log_id=validation_log_id,
        gate_id=gate_id,
        gate_access_granted=granted,
        gate_access_message=message,
        created_at=datetime.utcnow(),
    )
    db.session.add(gate_log)


def _create_ticket_gate_log(ticket_obj: Ticket, gate_id: int, status: str, message: str):
    log = TicketGateValidationLog(
        ticket_id=ticket_obj.id,
        gate_id=gate_id,
        validator_id=current_user.id,
        validation_status=status,
        validation_message=message,
        created_at=datetime.utcnow(),
    )
    db.session.add(log)
    return log


def _gate_allows(pass_obj: EventPass, gate_id: int):
    """
    Return (allowed: bool, message: str, gate: Gate|None)
    """
    gate = Gate.query.get(gate_id)
    if not gate or not gate.is_active:
        return False, "Gate not found or inactive", None

    # gate must match the same event
    if gate.event_id != pass_obj.event_id:
        pass_event = pass_obj.event.event_name if pass_obj.event else f'Event #{pass_obj.event_id}'
        gate_event_obj = Event.query.get(gate.event_id)
        gate_event = gate_event_obj.event_name if gate_event_obj else f'Event #{gate.event_id}'
        return False, (
            f'Wrong event pass. This pass is for "{pass_event}" '
            f'but selected gate is for "{gate_event}".'
        ), gate

    # Check access rule
    rule = GateAccessRule.query.filter_by(
        gate_id=gate_id,
        pass_type_id=pass_obj.pass_type_id
    ).first()

    if not rule:
        # Legacy fallback: if a gate has zero rules configured, allow all pass types.
        # This keeps older data usable while still enforcing explicit rules once configured.
        gate_rule_count = GateAccessRule.query.filter_by(gate_id=gate_id).count()
        if gate_rule_count == 0:
            return True, "Gate access allowed (no explicit rules configured)", gate

        return False, "No access rule for this pass type at this gate", gate

    if not rule.can_access:
        return False, "Access denied for this pass type at this gate", gate

    return True, "Gate access allowed", gate


def _validate_ticket_for_gate(ticket_obj: Ticket, gate_id: int, gate_obj=None):
    gate_obj = gate_obj or Gate.query.get(gate_id)
    if not gate_obj or not gate_obj.is_active:
        return jsonify({"success": False, "message": "Gate not found or inactive"}), 400

    if not user_can_scan_gate(current_user, gate_obj):
        return jsonify({"success": False, "message": "You are not assigned to this gate."}), 403

    ticket_event = _ticket_event(ticket_obj)
    if not ticket_event:
        return jsonify({"success": False, "message": "Ticket is missing event mapping"}), 400

    gate_event_obj = Event.query.get(gate_obj.event_id)
    gate_event_name = gate_event_obj.event_name if gate_event_obj else f'Event #{gate_obj.event_id}'

    if gate_obj.event_id != ticket_event.id:
        try:
            _create_ticket_gate_log(
                ticket_obj,
                gate_id,
                'failed',
                f'Wrong event ticket. Ticket event "{ticket_event.event_name}", gate event "{gate_event_name}".'
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({
            "success": False,
            "message": (
                f'Wrong event ticket. This ticket belongs to "{ticket_event.event_name}" '
                f'but selected gate is for "{gate_event_name}".'
            ),
            "event_mismatch": True,
            "selected_gate_event": gate_event_name,
            "pass_event": ticket_event.event_name,
            "pass_info": {
                "participant_name": ticket_obj.ticket_code,
                "pass_type": "Batch Ticket",
                "event": ticket_event.event_name,
            },
            "ticket_hint": {
                "ticket_code": ticket_obj.ticket_code,
                "barcode": ticket_obj.barcode,
                "event_id": ticket_event.id,
                "event_name": ticket_event.event_name,
            }
        }), 403

    if ticket_obj.status == 'used':
        try:
            _create_ticket_gate_log(ticket_obj, gate_id, 'duplicate', 'Duplicate scan (ticket already used)')
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Ticket already used",
            "pass_info": {
                "participant_name": ticket_obj.ticket_code,
                "pass_type": "Batch Ticket",
                "event": ticket_event.event_name,
            }
        }), 400

    if ticket_obj.status == 'expired':
        try:
            _create_ticket_gate_log(ticket_obj, gate_id, 'failed', 'Ticket expired')
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Ticket has expired",
            "pass_info": {
                "participant_name": ticket_obj.ticket_code,
                "pass_type": "Batch Ticket",
                "event": ticket_event.event_name,
            }
        }), 400

    try:
        ticket_obj.status = 'used'
        ticket_obj.scanned_by = current_user.username
        ticket_obj.scanned_at = datetime.utcnow()
        _create_ticket_gate_log(ticket_obj, gate_id, 'success', 'Ticket entry approved')
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Validation error occurred"}), 500

    return jsonify({
        "success": True,
        "message": "Ticket entry approved",
        "pass_info": {
            "participant_name": ticket_obj.ticket_code,
            "pass_type": "Batch Ticket",
            "event": ticket_event.event_name,
            "validated_at": ticket_obj.scanned_at.strftime("%Y-%m-%d %H:%M:%S"),
            "gate_id": gate_id
        },
        "ticket_info": {
            "ticket_code": ticket_obj.ticket_code,
            "barcode": ticket_obj.barcode,
            "status": ticket_obj.status
        }
    }), 200


@validation_bp.route("/validate", methods=["GET", "POST"])
@login_required
def validate_pass():
    if request.method == "GET":
        events = get_scannable_active_events(current_user)
        return render_template("validation/scanner.html", events=events)

    data = request.get_json(silent=True) or {}
    scanned_code = _normalize_scanned_code(data.get("code") or "")
    gate_id = data.get("gate_id")

    if not scanned_code:
        return jsonify({"success": False, "message": "No code provided"}), 400

    if not gate_id:
        return jsonify({"success": False, "message": "gate_id is required"}), 400

    try:
        gate_id = int(gate_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "gate_id must be a valid integer"}), 400

    gate_for_scanner = Gate.query.get(gate_id)
    if not gate_for_scanner or not gate_for_scanner.is_active:
        return jsonify({"success": False, "message": "Gate not found or inactive"}), 400

    if not user_can_scan_gate(current_user, gate_for_scanner):
        return jsonify({"success": False, "message": "You are not assigned to this gate."}), 403

    pass_obj = _resolve_pass(scanned_code)
    if not pass_obj:
        ticket_obj = _resolve_ticket(scanned_code)
        if ticket_obj:
            return _validate_ticket_for_gate(ticket_obj, gate_id, gate_for_scanner)

        return jsonify({"success": False, "message": "Invalid code or pass/ticket not found"}), 404

    # Expiry check (server-side)
    now = datetime.utcnow()
    if pass_obj.expires_at and now > pass_obj.expires_at:
        try:
            log = _create_validation_log(pass_obj, "failed", "Pass expired")
            _create_gate_log(log.id, int(gate_id), False, "Expired pass")
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"success": False, "message": "Pass expired"}), 400

    # Gate access check BEFORE marking validated
    allowed, gate_msg, gate_obj = _gate_allows(pass_obj, gate_id)
    if not allowed:
        try:
            log = _create_validation_log(pass_obj, "failed", f"Gate denied: {gate_msg}")
            _create_gate_log(log.id, gate_id, False, gate_msg)
            db.session.commit()
        except Exception:
            db.session.rollback()

        pass_event = pass_obj.event.event_name if pass_obj.event else f'Event #{pass_obj.event_id}'
        gate_event_name = None
        if gate_obj:
            gate_event_obj = Event.query.get(gate_obj.event_id)
            gate_event_name = gate_event_obj.event_name if gate_event_obj else None

        return jsonify({
            "success": False,
            "message": gate_msg,
            "pass_info": {
                "participant_name": pass_obj.participant_name,
                "pass_type": pass_obj.pass_type.type_name if pass_obj.pass_type else "Unknown",
                "event": pass_event,
            },
            "event_mismatch": bool(gate_obj and gate_obj.event_id != pass_obj.event_id),
            "selected_gate_event": gate_event_name,
            "pass_event": pass_event,
        }), 403

    # ATOMIC validation update to prevent double entry
    try:
        rows = (
            db.session.query(EventPass)
            .filter(EventPass.id == pass_obj.id, EventPass.is_validated == False)  # noqa: E712
            .update(
                {
                    EventPass.is_validated: True,
                    EventPass.validation_count: EventPass.validation_count + 1,
                },
                synchronize_session=False,
            )
        )

        if rows == 0:
            log = _create_validation_log(pass_obj, "duplicate", "Duplicate scan (already validated)")
            _create_gate_log(log.id, gate_id, False, "Duplicate scan")
            db.session.commit()

            return jsonify({
                "success": False,
                "message": "Pass already validated",
                "pass_info": {
                    "participant_name": pass_obj.participant_name,
                    "pass_type": pass_obj.pass_type.type_name if pass_obj.pass_type else "Unknown",
                    "event": pass_obj.event.event_name if pass_obj.event else "Unknown",
                }
            }), 400

        log = _create_validation_log(pass_obj, "success", "Pass validated successfully")
        _create_gate_log(log.id, gate_id, True, "Entry approved")
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Entry approved",
            "pass_info": {
                "id": pass_obj.id,
                "participant_name": pass_obj.participant_name,
                "email": pass_obj.participant_email,
                "phone": pass_obj.participant_phone,
                "pass_type": pass_obj.pass_type.type_name if pass_obj.pass_type else "Unknown",
                "event": pass_obj.event.event_name if pass_obj.event else "Unknown",
                "validated_at": log.validation_time.strftime("%Y-%m-%d %H:%M:%S"),
                "gate_id": gate_id
            }
        }), 200

    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Validation error occurred"}), 500
