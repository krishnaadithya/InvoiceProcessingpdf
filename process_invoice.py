#!/usr/bin/env python3
"""
Unified invoice processing script that handles both PDF and Excel files.
"""

import os
import sys
# Add the project root directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import logging
from typing import Optional
from pathlib import Path
import argparse
import tempfile
from dotenv import load_dotenv

# Import document processing functions
from process_pdf_with_headers import process_pdf_with_headers
from src.excel_to_pdf import excel_to_pdf, convert_xls_to_xlsx
from src.docx_to_pdf import docx_to_pdf
from src.txt_to_pdf import txt_to_pdf

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_google_client():
    """Set up and return the Google Generative AI client."""
    try:
        from google import genai
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY environment variable not set. PDF processing with LLM will not be available.")
            return None
        
        return genai.Client(api_key=api_key)
    except ImportError:
        logger.warning("google-generativeai package not installed. PDF processing with LLM will not be available.")
        return None
    except Exception as e:
        logger.error(f"Error setting up Google client: {str(e)}")
        return None

def save_to_json(invoice_data, input_file_path: str) -> str:
    """
    Save the invoice data to a JSON file in the 'result' directory.
    
    Args:
        invoice_data: The invoice data to save (can be a dictionary or an object)
        input_file_path: The path to the input file
        
    Returns:
        The path to the saved JSON file
    """
    # Create result directory if it doesn't exist
    result_dir = "result"
    os.makedirs(result_dir, exist_ok=True)
    
    # Get the base filename without extension
    base_filename = os.path.splitext(os.path.basename(input_file_path))[0]
    
    # Create the output JSON file path
    output_file_path = os.path.join(result_dir, f"{base_filename}.json")
    
    # Convert invoice data to JSON-serializable format
    # Check if invoice_data is a dictionary or an object
    if isinstance(invoice_data, dict):
        # It's already a dictionary, just ensure items are serializable
        json_data = invoice_data
    else:
        # It's an object, convert to dictionary
        json_data = {
            "headers": invoice_data.headers if hasattr(invoice_data, 'headers') else [],
            "items": [item.model_dump() if hasattr(item, 'model_dump') else item.dict() 
                     for item in invoice_data.items]
        }
    
    # Write to JSON file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved invoice data to {output_file_path}")
    return output_file_path

def process_file(file_path: str) -> None:
    """
    Process an invoice file (PDF, Excel, or Document) and print the extracted data.
    
    Args:
        file_path: Path to the invoice file
    """
    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return
    
    file_ext = os.path.splitext(file_path)[1].lower()
    
    llm_client = setup_google_client()

    temp_pdf_path = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf').name

    
    if file_ext in ['.xlsx', '.xls']:
        # Process Excel file
        if file_ext == '.xls':
            file_path = convert_xls_to_xlsx(file_path, temp_pdf_path.replace('.pdf', '.xlsx'))
        
        temp_pdf_path = excel_to_pdf(file_path, pdf_path=temp_pdf_path)

        invoice_data_obj = process_pdf_with_headers(temp_pdf_path)
        
        # Convert the InvoiceData object to the format expected by the rest of the code
        invoice_data = {
            "headers": invoice_data_obj.headers,
            "items": [item.model_dump() if hasattr(item, 'model_dump') else item.dict() for item in invoice_data_obj.items]
        }

                                      
    elif file_ext == '.pdf':
    
        try:
            logger.info(f"Processing PDF file with header context: {file_path}")
            
            # Process the PDF using process_pdf_with_headers
            invoice_data_obj = process_pdf_with_headers(file_path)
            
            # Convert the InvoiceData object to the format expected by the rest of the code
            invoice_data = {
                "headers": invoice_data_obj.headers,
                "items": [item.model_dump() if hasattr(item, 'model_dump') else item.dict() for item in invoice_data_obj.items]
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF with headers: {str(e)}")
                
    elif file_ext in ['.doc', '.docx', '.txt']:
        # Process Document file by first converting to PDF
        # Ensure the required modules are imported
        if file_ext == '.txt':
            temp_pdf_path = txt_to_pdf(file_path, temp_pdf_path)
            logger.info(f"Converted text file to PDF: {temp_pdf_path}")
        elif file_ext in ['.doc', '.docx']:
            temp_pdf_path = docx_to_pdf(file_path, temp_pdf_path)
            logger.info(f"Converted document file to PDF: {temp_pdf_path}")
        
        invoice_data_obj = process_pdf_with_headers(temp_pdf_path)
        
        # Convert the InvoiceData object to the format expected by the rest of the code
        invoice_data = {
            "headers": invoice_data_obj.headers,
            "items": [item.model_dump() if hasattr(item, 'model_dump') else item.dict() for item in invoice_data_obj.items]
        }
        
    else:
        logger.error(f"Unsupported file format: {file_ext}")
        logger.error("Supported formats: .pdf, .xlsx, .xls, .doc, .docx, .txt")
        return
    
    json_path = save_to_json(invoice_data, file_path)
    print(f"Results saved to: {json_path}")
    
    # Print results
    if isinstance(invoice_data, dict):
        # It's a dictionary
        items_count = len(invoice_data.get('items', []))
        items = invoice_data.get('items', [])
        print(f"\nExtracted {items_count} items from {file_path}:")
        for i, item in enumerate(items, 1):
            print(f"\nItem {i}:")
            print(f"  Product: {item.get('product_name', 'N/A')}")
            print(f"  Batch Number: {item.get('batch_number', 'N/A')}")
            print(f"  Expiry: {item.get('expiry_date', 'N/A')}")
            print(f"  MRP: {item.get('mrp', 'N/A')}")
            print(f"  Quantity: {item.get('quantity', 'N/A')}")
    else:
        # It's an object (likely a Pydantic model)
        items_count = len(invoice_data.items) if hasattr(invoice_data, 'items') else 0
        print(f"\nExtracted {items_count} items from {file_path}:")
        for i, item in enumerate(invoice_data.items if hasattr(invoice_data, 'items') else [], 1):
            print(f"\nItem {i}:")
            print(f"  Product: {getattr(item, 'product_name', 'N/A')}")
            print(f"  Batch Number: {getattr(item, 'batch_number', 'N/A')}")
            print(f"  Expiry: {getattr(item, 'expiry_date', 'N/A')}")
            print(f"  MRP: {getattr(item, 'mrp', 'N/A')}")
            print(f"  Quantity: {getattr(item, 'quantity', 'N/A')}")
    return json_path

def main():
    """Main function to parse arguments and process files."""
    parser = argparse.ArgumentParser(description="Process invoice files (PDF, Excel, XLS)")
    parser.add_argument("file_path", help="Path to the invoice file")
    
    args = parser.parse_args()
    
    try:
        process_file(args.file_path)
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 