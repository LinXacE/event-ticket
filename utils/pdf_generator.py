from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from PIL import Image
import os

def generate_pdf_ticket(pass_obj, event, qr_code_path, output_dir='static/pdfs'):
    """
    Generate a PDF ticket with QR code and event details
    
    Args:
        pass_obj: EventPass object
        event: Event object
        qr_code_path: Path to QR code image
        output_dir: Directory to save PDF
    
    Returns:
        str: Path to generated PDF file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate PDF filename
    pdf_filename = f"ticket_{pass_obj.pass_code}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    
    # Create PDF canvas
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    
    # Set up colors
    header_color = colors.HexColor('#2C3E50')
    text_color = colors.HexColor('#34495E')
    accent_color = colors.HexColor('#3498DB')
    
    # Draw header background
    c.setFillColor(header_color)
    c.rect(0, height - 2*inch, width, 2*inch, fill=True, stroke=False)
    
    # Event title
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 24)
    c.drawCentredString(width/2, height - 1*inch, 'EVENT TICKET')
    
    # Event name
    c.setFont('Helvetica', 18)
    c.drawCentredString(width/2, height - 1.5*inch, event.event_name)
    
    # Draw ticket body
    c.setFillColor(text_color)
    
    # Participant information
    y_position = height - 3*inch
    c.setFont('Helvetica-Bold', 14)
    c.drawString(1*inch, y_position, 'Participant Information:')
    
    y_position -= 0.4*inch
    c.setFont('Helvetica', 12)
    c.drawString(1*inch, y_position, f'Name: {pass_obj.participant_name}')
    
    y_position -= 0.3*inch
    c.drawString(1*inch, y_position, f'Email: {pass_obj.participant_email or "N/A"}')
    
    y_position -= 0.3*inch
    c.drawString(1*inch, y_position, f'Phone: {pass_obj.participant_phone or "N/A"}')
    
    y_position -= 0.3*inch
    c.drawString(1*inch, y_position, f'Pass Type: {pass_obj.pass_type.type_name if pass_obj.pass_type else "N/A"}')
    
    # Event details
    y_position -= 0.6*inch
    c.setFont('Helvetica-Bold', 14)
    c.drawString(1*inch, y_position, 'Event Details:')
    
    y_position -= 0.4*inch
    c.setFont('Helvetica', 12)
    c.drawString(1*inch, y_position, f'Date: {event.event_date.strftime("%B %d, %Y")}')
    
    y_position -= 0.3*inch
    c.drawString(1*inch, y_position, f'Time: {event.event_time.strftime("%I:%M %p")}')
    
    y_position -= 0.3*inch
    c.drawString(1*inch, y_position, f'Location: {event.location}')
    
    # Add QR code
    if os.path.exists(qr_code_path):
        # Position QR code on the right side
        qr_size = 2.5*inch
        qr_x = width - qr_size - 1*inch
        qr_y = height - 6*inch
        
        # Draw QR code border
        c.setStrokeColor(accent_color)
        c.setLineWidth(2)
        c.rect(qr_x - 0.1*inch, qr_y - 0.1*inch, qr_size + 0.2*inch, qr_size + 0.2*inch)
        
        # Add QR code image
        c.drawImage(qr_code_path, qr_x, qr_y, width=qr_size, height=qr_size)
        
        # QR code label
        c.setFont('Helvetica-Bold', 10)
        c.drawCentredString(qr_x + qr_size/2, qr_y - 0.3*inch, 'Scan for Entry')
    
    # Add pass code
    y_position -= 0.6*inch
    c.setFont('Helvetica-Bold', 10)
    c.drawString(1*inch, y_position, f'Pass Code: {pass_obj.pass_code}')
    
    # Footer
    c.setFont('Helvetica', 8)
    c.setFillColor(colors.grey)
    c.drawCentredString(width/2, 0.5*inch, 'Please present this ticket at the event entrance')
    c.drawCentredString(width/2, 0.3*inch, 'Event Access Control System')
    
    # Save PDF
    c.save()
    
    return pdf_path

def generate_batch_pdf_tickets(passes, event, output_dir='static/pdfs'):
    """
    Generate PDF tickets for multiple passes
    
    Args:
        passes: List of EventPass objects
        event: Event object
        output_dir: Directory to save PDFs
    
    Returns:
        list: List of paths to generated PDF files
    """
    pdf_paths = []
    
    for pass_obj in passes:
        if pass_obj.qr_code_path and os.path.exists(pass_obj.qr_code_path):
            pdf_path = generate_pdf_ticket(pass_obj, event, pass_obj.qr_code_path, output_dir)
            pdf_paths.append(pdf_path)
    
    return pdf_paths
