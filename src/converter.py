from docx2pdf import convert
from pdf2docx import Converter
import os

def docx_to_pdf(input_path, output_path):
    try:
        convert(input_path, output_path)
        return True
    except Exception as e:
        print(e)
        return False

def pdf_to_docx(input_path, output_path):
    try:
        cv = Converter(input_path)
        cv.convert(output_path, start=0, end=None)
        cv.close()
        return True
    except Exception as e:
        print(e)
        return False