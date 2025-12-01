import qrcode
from PIL import Image, ImageDraw, ImageFont
import os
from cryptography.fernet import Fernet
import hashlib
import base64

def generate_encryption_key(secret_key):
    """Generate a Fernet key from the secret key"""
    key = hashlib.sha256(secret_key.encode()).digest()
    return base64.urlsafe_b64encode(key)

def encrypt_data(data, secret_key):
    """Encrypt data using Fernet symmetric encryption"""
    key = generate_encryption_key(secret_key)
    f = Fernet(key)
    encrypted = f.encrypt(data.encode())
    return encrypted.decode()

def decrypt_data(encrypted_data, secret_key):
    """Decrypt data using Fernet symmetric encryption"""
    try:
        key = generate_encryption_key(secret_key)
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception as e:
        return None

def generate_qr_code(data, filename, save_path='static/qr_codes/', logo_path=None):
    """
    Generate QR code with optional logo
    
    Args:
        data: The data to encode in the QR code
        filename: The name of the output file
        save_path: Directory to save the QR code
        logo_path: Optional path to logo image to add to center
    
    Returns:
        The full path to the generated QR code
    """
    # Create directory if it doesn't exist
    os.makedirs(save_path, exist_ok=True)
    
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    
    # Add data
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.convert('RGB')
    
    # Add logo if provided
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path)
        
        # Calculate logo size (15% of QR code)
        qr_width, qr_height = img.size
        logo_size = int(qr_width * 0.15)
        
        # Resize logo
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
        
        # Calculate position (center)
        logo_pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
        
        # Paste logo
        img.paste(logo, logo_pos)
    
    # Save image
    full_path = os.path.join(save_path, filename)
    img.save(full_path)
    
    return full_path

def generate_pass_code(event_id, pass_type, participant_id):
    """Generate a unique pass code"""
    import time
    timestamp = int(time.time() * 1000)
    code = f"EVT{event_id:04d}-{pass_type[:3].upper()}-{participant_id:06d}-{timestamp}"
    return code

def create_event_pass_qr(pass_data, pass_code, event_name, participant_name, pass_type, secret_key):
    """
    Create a complete event pass QR code with encrypted data
    
    Args:
        pass_data: Dictionary containing pass information
        pass_code: The unique pass code
        event_name: Name of the event
        participant_name: Name of the participant
        pass_type: Type of pass (Judge, Mentor, etc.)
        secret_key: Secret key for encryption
    
    Returns:
        Tuple of (qr_code_path, encrypted_data)
    """
    # Convert pass data to string
    data_string = f"{pass_code}|{pass_data.get('event_id')}|{pass_data.get('participant_id')}|{pass_data.get('pass_type_id')}"
    
    # Encrypt the data
    encrypted_data = encrypt_data(data_string, secret_key)
    
    # Generate QR code filename
    filename = f"pass_{pass_code}.png"
    
    # Generate QR code
    qr_path = generate_qr_code(encrypted_data, filename)
    
    return qr_path, encrypted_data
