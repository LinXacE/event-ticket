import barcode
from barcode.writer import ImageWriter
import os
from PIL import Image, ImageDraw, ImageFont
from flask import current_app, has_app_context

def generate_barcode(data, filename, save_path='static/barcodes/', barcode_type='code128'):
    """
    Generate barcode image
    
    Args:
        data: The data to encode in the barcode
        filename: The name of the output file (without extension)
        save_path: Directory to save the barcode
        barcode_type: Type of barcode (code128, ean13, etc.)
    
    Returns:
        The full path to the generated barcode
    """
    save_dir, relative_prefix = _resolve_save_dir(save_path, 'barcodes')
    
    # Get barcode class
    barcode_class = barcode.get_barcode_class(barcode_type)
    
    # Create barcode instance
    barcode_instance = barcode_class(data, writer=ImageWriter())
    
    # Set options
    options = {
        'module_width': 0.3,
        'module_height': 15.0,
        'quiet_zone': 6.5,
        'font_size': 10,
        'text_distance': 5.0,
        'background': 'white',
        'foreground': 'black',
    }
    
    # Save barcode
    full_path = os.path.join(save_dir, filename)
    saved_file = barcode_instance.save(full_path, options=options)

    if relative_prefix:
        return f"{relative_prefix}/{os.path.basename(saved_file)}".replace("\\", "/")

    return saved_file

def create_event_pass_barcode(pass_code, event_name, participant_name, pass_type):
    """
    Create a barcode for event pass
    
    Args:
        pass_code: The unique pass code
        event_name: Name of the event
        participant_name: Name of the participant  
        pass_type: Type of pass (Judge, Mentor, etc.)
    
    Returns:
        The full path to the generated barcode
    """
    # Generate barcode filename
    filename = f"pass_{pass_code}"
    
    # Generate barcode
    barcode_path = generate_barcode(pass_code, filename)
    
    return barcode_path

def generate_batch_barcodes(pass_codes, save_path='static/barcodes/'):
    """
    Generate multiple barcodes at once
    
    Args:
        pass_codes: List of pass codes to generate barcodes for
        save_path: Directory to save the barcodes
    
    Returns:
        List of paths to generated barcodes
    """
    barcode_paths = []
    
    for code in pass_codes:
        filename = f"pass_{code}"
        try:
            path = generate_barcode(code, filename, save_path)
            barcode_paths.append(path)
        except Exception as e:
            print(f"Error generating barcode for {code}: {e}")
            barcode_paths.append(None)
    
    return barcode_paths


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
