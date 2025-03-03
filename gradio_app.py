#!/usr/bin/env python3
"""
Gradio web interface for invoice processing system.
This UI allows users to upload invoice files (PDF, DOCX, TXT, etc.) and download the results as CSV.
"""

import os
import sys
import csv
import tempfile
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import gradio as gr
from gradio_pdf import PDF  # Import the enhanced PDF component
from dotenv import load_dotenv

# Import the invoice processing functionality
from process_invoice import process_file, setup_google_client
# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check if Google API is available
GOOGLE_API_AVAILABLE = setup_google_client() is not None

def convert_to_csv(invoice_data: Dict) -> str:
    """
    Convert invoice data to CSV format.
    
    Args:
        invoice_data: Dictionary containing invoice data
        
    Returns:
        Path to the generated CSV file
    """
    # Create a temporary file for the CSV
    fd, temp_csv_path = tempfile.mkstemp(suffix='.csv')
    os.close(fd)
    
    # Extract items from invoice data
    items = invoice_data.get('items', [])
    
    if not items:
        logger.warning("No items found in invoice data")
        return temp_csv_path
    
    # Get all unique keys from all items to use as headers
    all_keys = set()
    for item in items:
        all_keys.update(item.keys())
    
    # Write to CSV
    with open(temp_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=sorted(all_keys))
        writer.writeheader()
        writer.writerows(items)
    
    logger.info(f"CSV file created at {temp_csv_path}")
    return temp_csv_path

def process_invoice_file(
    file_obj: tempfile._TemporaryFileWrapper,
    use_llm: bool = True
) -> Tuple[Dict, str, str, Optional[str], Optional[str]]:
    """
    Process an uploaded invoice file and return the results.
    
    Args:
        file_obj: The uploaded file object
        use_llm: Whether to use LLM for processing
        
    Returns:
        Tuple containing:
        - Dictionary of extracted data
        - HTML table for display
        - Status message
        - Path to CSV file (or None if processing failed)
        - Path to PDF file for display (or None if not a PDF)
    """
    if not file_obj:
        return {}, "", "No file uploaded", None, None
    
    # Get the file extension
    file_path = file_obj.name
    file_ext = os.path.splitext(file_path)[1].lower()
    
    # Check if file format is supported
    supported_formats = ['.pdf', '.xlsx', '.xls', '.doc', '.docx', '.txt']
    if file_ext not in supported_formats:
        return {}, "", f"Unsupported file format: {file_ext}. Supported formats: {', '.join(supported_formats)}", None, None
    
    # Process the file
    logger.info(f"Processing file: {file_path}")
    
    # Create a temporary directory for JSON output
    result_dir = Path("result")
    result_dir.mkdir(exist_ok=True)
    
    # For PDF display
    pdf_path = file_path
    
    # If the file is not a PDF, convert it to PDF for display
    if file_ext != '.pdf':
        temp_pdf = None
        try:
            if file_ext in ['.xlsx', '.xls']:
                from src.excel_to_pdf import excel_to_pdf, convert_xls_to_xlsx
                if file_ext == '.xls':
                    xlsx_path = convert_xls_to_xlsx(file_path, tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx').name)
                    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf').name
                    pdf_path = excel_to_pdf(xlsx_path, pdf_path=temp_pdf)
                else:
                    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf').name
                    pdf_path = excel_to_pdf(file_path, pdf_path=temp_pdf)
            elif file_ext in ['.doc', '.docx']:
                from src.docx_to_pdf import docx_to_pdf
                temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf').name
                pdf_path = docx_to_pdf(file_path, temp_pdf)
            elif file_ext == '.txt':
                from src.txt_to_pdf import txt_to_pdf
                temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf').name
                pdf_path = txt_to_pdf(file_path, temp_pdf)
            
            logger.info(f"Converted {file_ext} file to PDF: {pdf_path}")
        except Exception as e:
            logger.error(f"Error converting file to PDF: {str(e)}")
            pdf_path = None
    
    json_path = process_file(file_path)
    
    # Try to read the JSON file that was created
    if os.path.exists(json_path):
        import json
        with open(json_path, 'r', encoding='utf-8') as f:
            invoice_data = json.load(f)
    else:
        return {}, "", "Failed to process file. No output data found.", None, pdf_path
    
    # Create a DataFrame for display
    items = invoice_data.get('items', [])
    if 'error' in invoice_data and invoice_data['error']:
        html_table = f"<p class='error' style='color: red; font-weight: bold;'>{invoice_data['error']}</p>"
        status = f"Error: {invoice_data['error']}"
        # Still create CSV with any available items
        csv_path = convert_to_csv(invoice_data)
        return invoice_data, html_table, status, csv_path, pdf_path
    elif items:
        df = pd.DataFrame(items)
        html_table = df.to_html(classes='table table-striped')
        status = f"Successfully processed {len(items)} items from {os.path.basename(file_path)}"
        # Convert to CSV
        csv_path = convert_to_csv(invoice_data)
    else:
        html_table = "<p>No items found in the invoice</p>"
        status = "No items extracted from the file"
        # Create empty CSV
        csv_path = convert_to_csv({"items": []})
    
    return invoice_data, html_table, status, csv_path, pdf_path


def create_ui() -> gr.Blocks:
    """Create and return the Gradio UI."""
    with gr.Blocks(title="Invoice Processing System") as app:
        gr.Markdown("# Invoice Processing System")
        gr.Markdown("Upload an invoice file (PDF, Excel, Word, or Text) to extract and download the data as CSV.")
        
        with gr.Row():
            with gr.Column(scale=1):
                file_input = gr.File(label="Upload Invoice File")
                process_button = gr.Button("Process Invoice", variant="primary")
                status_output = gr.Textbox(label="Status", interactive=False)
                csv_output = gr.File(label="Download CSV", interactive=False)
            
            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.TabItem("Extracted Data"):
                        results_html = gr.HTML(label="Extracted Data")
                    with gr.TabItem("PDF View"):
                        # Use the enhanced PDF component from gradio_pdf
                        pdf_viewer = PDF(label="Invoice PDF", interactive=False)
        
        # Define the process flow
        process_button.click(
            fn=process_invoice_file,
            inputs=[file_input],
            outputs=[gr.State(), results_html, status_output, csv_output, pdf_viewer]
        )
        
        # Add examples if available
        example_dir = Path("examples")
        if example_dir.exists():
            example_files = list(example_dir.glob("*.pdf")) + list(example_dir.glob("*.xlsx"))
            if example_files:
                gr.Examples(
                    examples=[[str(f)] for f in example_files],
                    inputs=[file_input]
                )
    
    return app

def main():
    """Main function to launch the Gradio app."""
    app = create_ui()
    app.launch(
        server_name="0.0.0.0",  # Make accessible from other computers
        share=True,             # Create a public link
        inbrowser=True          # Open in browser
    )

if __name__ == "__main__":
    main()
