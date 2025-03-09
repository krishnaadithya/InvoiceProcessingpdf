import pandas as pd
import os
import json
import re
import concurrent.futures
from dotenv import load_dotenv
from google import genai
from typing import List, Dict, Any, Optional, Tuple
import logging
from pathlib import Path
import time
from process.invoice_prompts import get_extraction_prompt

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Rate limiter class for API calls
class RateLimiter:
    """Rate limiter for API calls to prevent exceeding quota."""
    def __init__(self, max_calls_per_minute: int = 15):
        self.max_calls_per_minute = max_calls_per_minute
        self.calls = []
        
    def wait_if_needed(self):
        """Wait if we're exceeding the rate limit."""
        current_time = time.time()
        # Remove calls older than 1 minute
        self.calls = [t for t in self.calls if current_time - t < 60]
        
        if len(self.calls) >= self.max_calls_per_minute:
            # Wait until we can make another call
            oldest_call = self.calls[0]
            sleep_time = 60 - (current_time - oldest_call)
            if sleep_time > 0:
                logger.info(f"Rate limit reached. Waiting for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
            
        # Record this call
        self.calls.append(time.time())

# Create a global rate limiter instance
rate_limiter = RateLimiter(max_calls_per_minute=15)


def setup_environment() -> None:
    """
    Load environment variables and configure the Gemini API client.
    
    Returns:
        None
    """
    load_dotenv()
    

def get_gemini_client() -> genai.Client:
    """
    Initialize and return a Gemini API client.
    
    Returns:
        genai.Client: Configured Gemini client
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    return genai.Client(api_key=api_key)


def process_chunk(chunk_info: Tuple[int, pd.DataFrame, int, int], client: genai.Client) -> List[Dict[str, Any]]:
    """
    Process a single chunk of data using Gemini API.
    
    Args:
        chunk_info: Tuple containing (chunk_index, dataframe_chunk, start_index, end_index)
        client: Gemini API client
        
    Returns:
        List of extracted items from the chunk
    """
    i, chunk_df, start_idx, end_idx = chunk_info
    
    # Use the imported prompt function
    extraction_prompt = get_extraction_prompt(start_idx, end_idx)
    
    chunk_items = []
    
    # Process chunk
    try:
        # Apply rate limiting before making the API call
        rate_limiter.wait_if_needed()
        
        chunk_response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[extraction_prompt, chunk_df.to_string()],
            config={
                'response_mime_type': 'application/json',
                'temperature': 0.1,
                'max_output_tokens': 8192,
            }
        )
        
        # Extract items
        chunk_text = chunk_response.text
        # Fix common JSON issues
        chunk_text = re.sub(r'[\n\r\t]', '', chunk_text)
        chunk_text = re.sub(r',\s*]', ']', chunk_text)
        
        # Extract JSON array
        match = re.search(r'\[(.*)\]', chunk_text, re.DOTALL)
        if match:
            try:
                chunk_items = json.loads('[' + match.group(1) + ']')
                logger.info(f"Successfully processed chunk {i+1} with {len(chunk_items)} items")
            except json.JSONDecodeError:
                logger.error(f"Error parsing JSON in chunk {i+1}")
        
    except Exception as e:
        logger.error(f"Error processing chunk {i+1}: {str(e)}")
    
    return chunk_items


def prepare_chunks(df: pd.DataFrame, chunk_size: int) -> List[Tuple[int, pd.DataFrame, int, int]]:
    """
    Prepare dataframe chunks for processing.
    
    Args:
        df: Input dataframe
        chunk_size: Size of each chunk
        
    Returns:
        List of chunk information tuples
    """
    num_chunks = (len(df) + chunk_size - 1) // chunk_size
    chunks_to_process = []
    
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = min((i + 1) * chunk_size, len(df))
        chunk_df = df.iloc[start_idx:end_idx]
        chunks_to_process.append((i, chunk_df, start_idx, end_idx))
    
    return chunks_to_process


def process_excel_file(file_path: str, output_path: str, chunk_size: int = 40, max_workers: int = 2) -> Dict[str, Any]:
    """
    Process an Excel file to extract product information using Gemini API.
    
    Args:
        file_path: Path to the Excel file
        output_path: Path to save the extracted data
        chunk_size: Size of each chunk for processing
        max_workers: Maximum number of parallel workers
        
    Returns:
        Dict containing the extraction results
    """
    # Setup environment
    setup_environment()
    client = get_gemini_client()
    
    # Read Excel file
    logger.info(f"Reading Excel file: {file_path}")
    df = pd.read_excel(file_path)
    
    # Prepare chunks for processing
    chunks_to_process = prepare_chunks(df, chunk_size)
    num_chunks = len(chunks_to_process)
    
    # Process chunks in parallel
    logger.info(f"Processing {num_chunks} chunks with {max_workers} workers")
    all_items = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Pass client to each process_chunk call
        results = list(executor.map(
            lambda chunk: process_chunk(chunk, client), 
            chunks_to_process
        ))
    
    # Combine results
    for chunk_items in results:
        all_items.extend(chunk_items)
    
    # Create final result
    final_result = {
        "items": all_items,
        "extraction_status": "COMPLETE" if all_items else "INCOMPLETE",
        "total_items": len(all_items)
    }
    
    # Save the final result
    with open(output_path, "w") as f:
        json.dump(final_result, f, indent=2)
    
    logger.info(f"Extraction complete. Total items extracted: {len(all_items)}")
    return final_result


def main() -> None:
    """
    Main function to run the Excel processing script.
    """
    input_file = 'expiry_invoice/SAC01000975.xls'
    output_file = "extracted_invoice_data.json"
    
    # Ensure the output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Process the Excel file
    result = process_excel_file(
        file_path=input_file,
        output_path=output_file,
        chunk_size=100,
        max_workers=2
    )
    
    print(f"Extraction complete. Total items extracted: {result['total_items']}")


if __name__ == "__main__":
    main()