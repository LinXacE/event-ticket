import qrcode
from PIL import Image
import os
from flask import current_app, has_app_context


def generate_qr_code(data, filename, save_path='static/qr_codes/', logo_path=None):
    """
    Generate QR code with optional logo
    """
    save_dir, relative_prefix = _resolve_save_dir(save_path, 'qr_codes')

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img = img.convert("RGB")

    # Add logo if provided
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path)

        qr_width, qr_height = img.size
        logo_size = int(qr_width * 0.15)

        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

        logo_pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
        img.paste(logo, logo_pos)

    full_path = os.path.join(save_dir, filename)
    img.save(full_path)

    if relative_prefix:
        return f"{relative_prefix}/{filename}".replace("\\", "/")
    return full_path


def generate_pass_code(event_id, pass_type, participant_id):
    """
    Generate a unique pass code
    """
    import time
    timestamp = int(time.time() * 1000)
    code = f"EVT{event_id:04d}-{pass_type[:3].upper()}-{participant_id:06d}-{timestamp}"
    return code


def create_event_pass_qr(pass_code, event_name, participant_name, pass_type):
    """
    Best practice:
    QR encodes ONLY pass_code (opaque token).
    Validation does all checks server-side using DB lookups.
    Returns: (qr_code_path, qr_payload)
    """
    filename = f"pass_{pass_code}.png"

    # QR payload contains only pass_code
    qr_payload = pass_code

    qr_path = generate_qr_code(qr_payload, filename)

    return qr_path, qr_payload


def _resolve_save_dir(save_path, default_subdir):
    """
    Resolve save directory against Flask static folder, not process CWD.
    This prevents broken images when server is started from another directory.
    """
    raw = (save_path or f'static/{default_subdir}').replace('\\', '/').strip()

    if has_app_context() and current_app.static_folder:
        static_root = current_app.static_folder
    else:
        static_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))

    if os.path.isabs(raw):
        absolute_dir = raw
        relative_prefix = None
    else:
        relative_dir = raw[7:] if raw.startswith('static/') else raw
        relative_dir = relative_dir.strip('/')
        absolute_dir = os.path.join(static_root, relative_dir)
        relative_prefix = f"static/{relative_dir}" if relative_dir else "static"

    os.makedirs(absolute_dir, exist_ok=True)
    return absolute_dir, relative_prefix
