import barcode
from barcode.writer import ImageWriter
import os
from PIL import Image, ImageDraw, ImageFont

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
    # Create directory if it doesn't exist
    os.makedirs(save_path, exist_ok=True)
    
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
    full_path = os.path.join(save_path, filename)
    barcode_instance.save(full_path, options=options)
    
    # The library adds .png extension automatically
    return f"{full_path}.png"

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
