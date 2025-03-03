import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def txt_to_pdf(input_txt, output_pdf=None):
    if output_pdf is None:
        output_pdf = os.path.splitext(input_txt)[0] + '.pdf'
    
    # Read the text file without modifying spacing
    with open(input_txt, "r", encoding="utf-8") as file:
        lines = file.readlines()
    
    c = canvas.Canvas(output_pdf, pagesize=letter)
    width, height = letter
    left_margin = 10
    top_margin = 10
    bottom_margin = 10
    line_height = 10  # Adjust based on desired spacing
    
    # Use a text object for more control
    text_object = c.beginText(left_margin, height - top_margin)
    text_object.setFont("Courier", 8)  # Use a monospaced font to keep spacing intact
    
    for line in lines:
        # Remove the newline, preserving other whitespace
        # And skip the line if it's empty (after stripping all whitespace)
        if not line.strip():
            continue
        line = line.rstrip("\n")
        text_object.textLine(line)
        
        # Check if we have reached the bottom margin
        if text_object.getY() < bottom_margin:
            c.drawText(text_object)
            c.showPage()
            text_object = c.beginText(left_margin, height - top_margin)
            text_object.setFont("Courier", 8)
    
    # Draw any remaining text
    c.drawText(text_object)
    c.save()
    return output_pdf