import os
import subprocess


def docx_to_pdf(input_file, output_file=None):
    #convert doc,docx into pdf
    # Ensure LibreOffice is installed and get absolute path
    input_path = os.path.abspath(input_file)
    output_dir = os.path.dirname(output_file)
    # Run LibreOffice command
    command = ["libreoffice", "--headless", "--convert-to", "pdf", input_path, "--outdir", output_dir]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    output_file_path = os.path.join(output_dir, os.path.basename(input_file).replace('.docx', '.pdf'))

    #rename the output file to the original file name
    os.rename(output_file_path, output_file)

    return output_file


