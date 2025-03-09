from google import genai
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Tuple
import pdf2image
import os
from pathlib import Path
import concurrent.futures
from dataclasses import dataclass
from functools import partial
import logging
from PIL import Image
from dotenv import load_dotenv
import gc
from itertools import islice


load_dotenv()


class InvoiceItem(BaseModel):
    """Represents a single item in an invoice."""
    product_name: str = Field(description="The name of the product")
    batch_number: str = Field(description="The batch number of the product")
    expiry_date: str = Field(description="The expiry date (format: MM/YY)")
    mrp: str = Field(description="Maximum Retail Price")
    quantity: int = Field(description="Product quantity")

class InvoiceData(BaseModel):
    """Represents the complete invoice data including headers."""
    headers: List[str] = Field(
        description="Column headers from the invoice table",
        default_factory=list
    )
    items: List[InvoiceItem] = Field(
        description="List of extracted invoice items",
        default_factory=list
    )

class HeaderExtraction(BaseModel):
    """Model for extracting headers separately."""
    headers: List[str] = Field(
        description="The column headers found in the invoice table"
    )

@dataclass
class PageData:
    """Container for page processing data."""
    idx: int
    image_path: str
    headers: List[str]
    items: List[InvoiceItem]

def extract_headers(client: genai.Client, image_path: str, model_id: str) -> List[str]:
    """
    Extract column headers from the first page of the invoice.
    
    Args:
        client: The Gemini API client
        image_path: Path to the image file
        model_id: The model ID to use for extraction
    
    Returns:
        List of column headers
    """
    header_prompt = """
    Extract only the column headers from this invoice table.
    Return them exactly as they appear, maintaining their order from left to right.
    Only extract the headers, not any data from the rows.
    """
    
    image_file = client.files.upload(
        file=image_path, 
        config={'display_name': 'invoice_header_page'}
    )

    response = client.models.generate_content(
        model=model_id,
        contents=[header_prompt, image_file],
        config={
            'response_mime_type': 'application/json',
            'response_schema': HeaderExtraction
        }
    )
    
    return response.parsed.headers if response.parsed else []

def setup_client() -> genai.Client:
    """Create and return a Gemini API client."""
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def save_image(image: Image, temp_dir: Path, idx: int) -> str:
    """
    Save a single page image to disk with optimized memory usage.
    
    Args:
        image: The PDF page image (PIL Image)
        temp_dir: Directory to save the image
        idx: Page index
    
    Returns:
        Path to the saved image
    """
    image_path = str(temp_dir / f"page_{idx+1}.jpg")
    
    # Optimize image for memory usage
    if image.mode in ('RGBA', 'LA'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    
    # Convert to grayscale to reduce memory usage
    image = image.convert('L')
    
    # Resize if the image is too large (max 2000px width while maintaining aspect ratio)
    if image.size[0] > 2000:
        ratio = 2000.0 / image.size[0]
        new_size = (2000, int(image.size[1] * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Save with optimized settings
    image.save(image_path, "JPEG", quality=85, optimize=True)
    
    # Clear the image from memory
    image = None
    gc.collect()
    
    return image_path

def process_single_page(
    page_data: Tuple[int, Image.Image, Path, List[str], genai.Client, str]
) -> PageData:
    """
    Process a single page of the PDF with optimized memory usage.
    
    Args:
        page_data: Tuple containing (page_index, page_image, temp_dir, headers, client, model_id)
    
    Returns:
        PageData object containing extracted information
    """
    idx, image, temp_dir, headers, client, model_id = page_data
    
    try:
        # Save image with optimization
        image_path = save_image(image, temp_dir, idx)
        
        # Clear the original image from memory
        image = None
        gc.collect()
        
        # First page: extract headers
        if idx == 0:
            headers = extract_headers(client, image_path, model_id)
            prompt = """
            Extract product details from this invoice table.
            Use the exact column headers you see in the table.
            """
        else:
            headers_str = ", ".join(headers)
            prompt = f"""
            Extract product details from this invoice table.
            This is page {idx + 1} of the same invoice.
            Use these column headers: {headers_str}
            Ensure the extracted data aligns with these columns in order.
            """
        
        # Process image with the API
        with open(image_path, 'rb') as img_file:
            image_file = client.files.upload(
                file=img_file,
                config={'display_name': f'invoice_page_{idx+1}'}
            )
        
        response = client.models.generate_content(
            model=model_id,
            contents=[prompt, image_file],
            config={
                'response_mime_type': 'application/json',
                'response_schema': InvoiceData
            }
        )
        
        items = response.parsed.items if response.parsed and response.parsed.items else []
        
        # Clean up response object
        response = None
        gc.collect()
        
        return PageData(idx=idx, image_path=image_path, headers=headers, items=items)
        
    except Exception as e:
        logging.error(f"Error processing page {idx}: {str(e)}")
        return PageData(idx=idx, image_path="", headers=headers, items=[])
    finally:
        # Ensure cleanup
        gc.collect()

def process_pdf_with_headers(pdf_path: str, max_workers: int = 3, batch_size: int = 2) -> InvoiceData:
    """
    Process a PDF invoice while preserving column header context using parallel processing.
    
    Args:
        pdf_path: Path to the PDF file
        max_workers: Maximum number of concurrent workers
        batch_size: Number of pages to process in each batch
    
    Returns:
        InvoiceData object containing headers and extracted items
    """
    # Convert PDF pages to images with memory-efficient batch processing
    images = []
    for batch in pdf2image.convert_from_path(pdf_path, size=(1700, None), fmt='jpeg', grayscale=True):
        images.append(batch)
        # Force garbage collection after each batch
        gc.collect()
    
    # Create temp directory with a more specific path
    temp_dir = Path("content/temp/pdf_processing")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize shared resources
    client = setup_client()
    model_id = "gemini-2.0-flash"
    headers: List[str] = []
    all_items: List[InvoiceItem] = []
    
    try:
        # Process first page separately to get headers
        first_page = process_single_page((0, images[0], temp_dir, headers, client, model_id))
        headers = first_page.headers
        all_items.extend(first_page.items)
        
        # Clear first page from memory
        images[0] = None
        gc.collect()
        
        # Process remaining pages in batches
        remaining_pages = list(enumerate(images[1:], start=1))
        for i in range(0, len(remaining_pages), batch_size):
            batch = remaining_pages[i:i + batch_size]
            
            # Process batch in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(batch))) as executor:
                future_to_page = {
                    executor.submit(process_single_page, (idx, img, temp_dir, headers, client, model_id)): idx
                    for idx, img in batch
                }
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_page):
                    page_idx = future_to_page[future]
                    try:
                        page_result = future.result()
                        all_items.extend(page_result.items)
                    except Exception as e:
                        logging.error(f"Error processing page {page_idx}: {str(e)}")
                    finally:
                        # Clear processed page from memory
                        images[page_idx] = None
                        gc.collect()
            
            # Force garbage collection after each batch
            gc.collect()
    
    finally:
        # Cleanup temporary files
        for file in temp_dir.glob("*.jpg"):
            try:
                file.unlink()
            except Exception as e:
                logging.warning(f"Failed to delete temporary file {file}: {str(e)}")
        
        # Try to remove the temp directory
        try:
            temp_dir.rmdir()
        except Exception as e:
            logging.warning(f"Failed to remove temporary directory: {str(e)}")
    
    return InvoiceData(headers=headers, items=all_items)

def main():
    """Main function to demonstrate usage."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        invoice_data = process_pdf_with_headers(
            "/Users/krishnaadithya/Desktop/dev/invoice_processing_2.0/pdf_only/expiry_invoice/DR REDDYS PE 1194.pdf",
            max_workers=3,  # Adjust based on your system and API limits
            batch_size=2  # Adjust based on your system and API limits
        )
        
        # Print headers
        print("Column Headers:", ", ".join(invoice_data.headers))
        print("\nExtracted Items:")
        
        # Print results
        for item in invoice_data.items:
            print(f"Product: {item.product_name}")
            print(f"Batch: {item.batch_number}")
            print(f"Expiry: {item.expiry_date}")
            print(f"MRP: {item.mrp}")
            print(f"Quantity: {item.quantity}")
            print("-" * 50)
            
    except Exception as e:
        logging.error(f"Error processing invoice: {str(e)}")

if __name__ == "__main__":
    main() 