import os
import subprocess
import logging

logger = logging.getLogger(__name__)

def docx_to_pdf(input_file, output_file=None):
    """
    Convert doc or docx file to PDF using LibreOffice.
    
    Args:
        input_file (str): Path to the input document file (.doc or .docx)
        output_file (str, optional): Path to the desired output PDF file
        
    Returns:
        str: Path to the output PDF file
        
    Raises:
        FileNotFoundError: If the input file doesn't exist
        RuntimeError: If the conversion fails
    """
    try:
        # Ensure input file exists
        if not os.path.exists(input_file):
            logger.error(f"Input file not found: {input_file}")
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        # Get absolute paths
        input_path = os.path.abspath(input_file)
        
        # If output_file is None, create one based on input file
        if output_file is None:
            output_file = os.path.splitext(input_path)[0] + '.pdf'
            
        output_dir = os.path.dirname(output_file)
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Run LibreOffice command
        logger.info(f"Converting {input_path} to PDF using LibreOffice")
        command = ["libreoffice", "--headless", "--convert-to", "pdf", input_path, "--outdir", output_dir]
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if process.returncode != 0:
            logger.error(f"LibreOffice conversion failed: {process.stderr}")
            raise RuntimeError(f"LibreOffice conversion failed: {process.stderr}")
        
        # LibreOffice creates the PDF with the same base name as the input file
        # Get the base name without extension and add .pdf
        input_basename = os.path.basename(input_path)
        input_name_without_ext = os.path.splitext(input_basename)[0]
        generated_pdf = os.path.join(output_dir, input_name_without_ext + '.pdf')
        
        # If the generated PDF doesn't exist, try with lowercase extension
        if not os.path.exists(generated_pdf):
            logger.warning(f"Generated PDF not found at expected path: {generated_pdf}")
            # Try to find the actual generated file
            for file in os.listdir(output_dir):
                if file.lower().startswith(input_name_without_ext.lower()) and file.lower().endswith('.pdf'):
                    generated_pdf = os.path.join(output_dir, file)
                    logger.info(f"Found generated PDF at: {generated_pdf}")
                    break
        
        # Rename the output file if needed
        if generated_pdf != output_file and os.path.exists(generated_pdf):
            logger.info(f"Renaming {generated_pdf} to {output_file}")
            os.rename(generated_pdf, output_file)
        elif not os.path.exists(generated_pdf):
            logger.error(f"Generated PDF not found: {generated_pdf}")
            raise FileNotFoundError(f"Generated PDF not found: {generated_pdf}")
        
        return output_file
        
    except Exception as e:
        logger.error(f"Error converting file to PDF: {str(e)}")
        raise


