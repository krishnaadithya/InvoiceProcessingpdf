"""
This module contains prompts for processing different types of invoices.
"""
from typing import List, Optional

def get_extraction_prompt(start_idx: int, end_idx: int) -> str:
    """
    Generate a prompt for extracting product information from a chunk of invoice data.
    
    Args:
        start_idx: Starting index of the chunk
        end_idx: Ending index of the chunk
        
    Returns:
        str: The extraction prompt
    """
    return f"""
    Extract product information from rows {start_idx} to {end_idx-1} in this invoice data.

    For each product row, extract:
    1. Product name
    2. Batch number
    3. Expiry date (MM/YY format)
    4. MRP (Maximum Retail Price)
    5. Quantity (as integer)
    
    Return ONLY a JSON array of objects, one for each product, with these properties:
    [
      {{
        "product_name": "...",
        "batch_number": "...",
        "expiry_date": "...",
        "mrp": "...",
        "quantity": ...
      }},
      ...
    ]
    
    Use null for any value you cannot extract. Return ONLY the JSON array.
    """

def get_header_extraction_prompt() -> str:
    """
    Generate a prompt for extracting headers from an invoice table.
    
    Returns:
        str: The header extraction prompt
    """
    return """
    Extract only the column headers from this invoice table.
    Return them exactly as they appear, maintaining their order from left to right.
    Only extract the headers, not any data from the rows.
    """

def get_pdf_first_page_prompt() -> str:
    """
    Generate a prompt for extracting product details from the first page of a PDF invoice.
    
    Returns:
        str: The first page extraction prompt
    """
    return """
    Extract product details from this invoice table.
    Use the exact column headers you see in the table.

    """

def get_pdf_subsequent_page_prompt(page_idx: int, headers: List[str]) -> str:
    """
    Generate a prompt for extracting product details from subsequent pages of a PDF invoice.
    
    Args:
        page_idx: The page index (0-based)
        headers: The column headers extracted from the first page
        
    Returns:
        str: The subsequent page extraction prompt
    """
    headers_str = ", ".join(headers)
    return f"""
    Extract product details from this invoice table.
    This is page {page_idx + 1} of the same invoice.
    Use these column headers: {headers_str}
    Ensure the extracted data aligns with these columns in order.

    Return ONLY a JSON array of objects, one for each product, with these properties:
    [
      {{
        "product_name": "...",
        "batch_number": "...",
        "expiry_date": "...",
        "mrp": "...",
        "quantity": ...
      }},
      ...
    ]
    
    Use null for any value you cannot extract. Return ONLY the JSON array.

    """

def get_custom_invoice_prompt(invoice_type: str, headers: Optional[List[str]] = None) -> str:
    """
    Generate a prompt for a custom invoice type.
    
    Args:
        invoice_type: The type of invoice (e.g., 'medical', 'retail', 'wholesale')
        headers: Optional list of headers to use
        
    Returns:
        str: A custom prompt for the specified invoice type
    """
    base_prompt = f"""
    Extract product details from this {invoice_type} invoice table.
    """
    
    if headers:
        headers_str = ", ".join(headers)
        base_prompt += f"""
        Use these column headers: {headers_str}
        Ensure the extracted data aligns with these columns in order.
        """
    else:
        base_prompt += """
        Use the exact column headers you see in the table.
        """
    
    return base_prompt 