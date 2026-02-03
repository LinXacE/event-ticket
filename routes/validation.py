from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from database import db
from models import (
    EventPass, ValidationLog,
    Gate, GateAccessRule, GateValidationLog
)
from datetime import datetime
import os
import json
from cryptography.fernet import Fernet, InvalidToken

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


def _resolve_pass(scanned_code: str):
    """
    New QR payload: pass_code only.
    Also supports legacy encrypted QR payloads if cipher exists.
    """
    # 1) direct pass_code lookup (new best practice)
    p = EventPass.query.filter_by(pass_code=scanned_code).first()
    if p:
        return p

    # 2) legacy decrypt support
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


def _gate_allows(pass_obj: EventPass, gate_id: int):
    """
    Return (allowed: bool, message: str)
    """
    gate = Gate.query.get(gate_id)
    if not gate or not gate.is_active:
        return False, "Gate not found or inactive"

    # gate must match the same event
    if gate.event_id != pass_obj.event_id:
        return False, "Gate does not belong to this event"

    # Check access rule
    rule = GateAccessRule.query.filter_by(
        gate_id=gate_id,
        pass_type_id=pass_obj.pass_type_id
    ).first()

    if not rule:
        return False, "No access rule for this pass type at this gate"

    if not rule.can_access:
        return False, "Access denied for this pass type at this gate"

    return True, "Gate access allowed"


@validation_bp.route("/validate", methods=["GET", "POST"])
@login_required
def validate_pass():
    if request.method == "GET":
        return render_template("validation/scanner.html")

    data = request.get_json(silent=True) or {}
    scanned_code = (data.get("code") or "").strip()
    gate_id = data.get("gate_id")

    if not scanned_code:
        return jsonify({"success": False, "message": "No code provided"}), 400

    if not gate_id:
        return jsonify({"success": False, "message": "gate_id is required"}), 400

    pass_obj = _resolve_pass(scanned_code)
    if not pass_obj:
        return jsonify({"success": False, "message": "Invalid code or pass not found"}), 404

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
    allowed, gate_msg = _gate_allows(pass_obj, int(gate_id))
    if not allowed:
        try:
            log = _create_validation_log(pass_obj, "failed", f"Gate denied: {gate_msg}")
            _create_gate_log(log.id, int(gate_id), False, gate_msg)
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({
            "success": False,
            "message": gate_msg,
            "pass_info": {
                "participant_name": pass_obj.participant_name,
                "pass_type": pass_obj.pass_type.type_name if pass_obj.pass_type else "Unknown",
                "event": pass_obj.event.event_name if pass_obj.event else "Unknown",
            }
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
            _create_gate_log(log.id, int(gate_id), False, "Duplicate scan")
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
        _create_gate_log(log.id, int(gate_id), True, "Entry approved")
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
                "gate_id": int(gate_id)
            }
        }), 200

    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Validation error occurred"}), 500
