# Invoice Processing System with Gradio UI

This system processes invoice files (PDF, Excel, Word, Text) and extracts structured data using a combination of OCR, regex patterns, and LLM-based extraction. The extracted data can be downloaded as CSV.

## Features

- **Multiple File Formats**: Supports PDF, Excel (.xlsx, .xls), Word (.doc, .docx), and Text (.txt) files
- **Document Conversion**: Automatically converts Word and Text files to PDF for processing
- **LLM-Enhanced Extraction**: Uses Google's Generative AI for improved extraction accuracy (optional)
- **Web Interface**: Easy-to-use Gradio UI for uploading files and downloading results
- **CSV Export**: Download extracted data as CSV for further analysis

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd invoice-processing-system
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Create a `.env` file in the project root
   - Add your Google API key for LLM processing:
     ```
     GOOGLE_API_KEY=your_api_key_here
     ```

## Usage

### Web Interface (Gradio UI)

1. Start the Gradio web interface:
   ```bash
   python gradio_app.py
   ```

2. Open your browser and navigate to the URL shown in the terminal (typically http://127.0.0.1:7860)

3. Upload an invoice file using the file upload button

4. Click "Process Invoice" to extract data from the file

5. View the extracted data in the table and download as CSV using the download button

### Command Line Interface

You can also use the command line interface:

```bash
# Process a file with default settings (using LLM if available)
python process_invoice.py path/to/invoice.pdf

# Process without using LLM
python process_invoice.py path/to/invoice.xlsx --no-llm

# Process without saving JSON output
python process_invoice.py path/to/invoice.docx --no-json
```

## Requirements

- Python 3.8+
- Google API key (for LLM-enhanced extraction)
- LibreOffice (for converting .doc/.docx files to PDF)
- Tesseract OCR (for PDF processing)

## Troubleshooting

- **LLM Processing Not Available**: Ensure your Google API key is correctly set in the `.env` file
- **PDF Conversion Issues**: Make sure LibreOffice is installed and accessible in your PATH
- **OCR Quality Issues**: Ensure Tesseract OCR is properly installed and configured

## License

[MIT License](LICENSE) 