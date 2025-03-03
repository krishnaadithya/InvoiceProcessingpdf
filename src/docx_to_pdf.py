import os
import subprocess
import aspose.words as aw

def docx_to_pdf(input_file, output_file=None):
    #convert doc,docx into pdf
    # Ensure LibreOffice is installed and get absolute path
    input_path = os.path.abspath(input_file)
    output_dir = os.path.dirname(input_path)  # Save in the same directory

    # Run LibreOffice command
    command = ["libreoffice", "--headless", "--convert-to", "pdf", input_path, "--outdir", output_dir]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Return output file path
    if output_file is None: 
      output_file = os.path.join(output_dir, os.path.splitext(os.path.basename(input_file))[0] + ".pdf")
    return output_file


def docx_to_pdf_(input_file, output_file=None):
    input_path = os.path.abspath(input_file)
    output_dir = os.path.dirname(input_path)  # Save in the same directory


    # Load .doc file
    doc = aw.Document(input_path)

    if output_file is None: 
      output_file = os.path.join(output_dir, os.path.splitext(os.path.basename(input_file))[0] + ".pdf")

    doc.save(output_file)

    return output_file
