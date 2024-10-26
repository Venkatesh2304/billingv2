from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import re

def collection(file):
    with open(file) as f:
        x1 = f.read()
        
    x = x1.split('\n')
    values = ['Region', 'Invoice No', 'Invoice Date', 'Retailer PAN']
    first, last, billval, invoice, name = [], [], [], [], []
    bill = ''
    
    # Read configuration file
    with open('config.txt') as f:
        config = eval(f.read())

    for i in range(len(x)):
        if 'Invoice No ' in x[i] and config['secname'] in x[i]:
            first.append(i)
            invoice.append(x[i])
        if 'Time of Billing ' in x[i]:
            last.append(i)
        if 'Bill Amount' in x[i]:
            billval.append(x[i])
        if 'Retailer ' in x[i] and 'Name' in x[i] and config['secadd'] in x[i]:
            name.append(x[i])
    
    data = []  # To hold table data
    for i in range(len(first)):
        # Prepare data for the table
        y1 = x[first[i]:last[i] + 1]
        for j in y1:
            bill += j + '\n'
            for t in values:
                if t in j:
                    if 'Time' not in j:
                        j = j.split(t)[0]
                    break
            # Add the processed paragraph (not used in table)
        
        bill_value = billval[i]
        bill_value_parts = bill_value.split('Bill')
        bill_value1 = bill_value_parts[0].strip()
        bill_value2 = 'Bill' + bill_value_parts[1]

        invoice_number = invoice[i].split('Invoice')[1].split(':')[1].strip()
        retailer_name = name[i].split(':')[1].strip()
        imp = f"{invoice_number} * {retailer_name} * Amt : {bill_value2.split(':')[1].strip()}"
        imp = ' '.join(imp.split())
        
        # Collecting data for the PDF table
        data.append([' ', imp, ' '])  # Placeholder for Date and Balance
        print( data )

    return data

class PDFReport:
    def __init__(self, filename):
        self.filename = filename
        self.document = SimpleDocTemplate(self.filename, pagesize=letter)
        self.story = []

    def add_invoice_table(self, data):
        styles = getSampleStyleSheet()
        normal_style = styles['Normal']
        normal_style.fontName = 'Courier New'
        normal_style.fontSize = 9
        normal_style.leading = 11

        # Create the table
        table_data = [['Date', 'Details', 'Balance']]  # Header row
        
        for entry in data:
            table_data.append(entry)

        # Create the table
        table = Table(table_data, colWidths=[1.5 * inch, 3 * inch, 1.5 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        self.story.append(table)

    def add_signature(self):
        styles = getSampleStyleSheet()
        signature_style = ParagraphStyle('SignatureStyle', parent=styles['Normal'], fontSize=12, alignment=2)
        signature_paragraph = Paragraph(' ' * 60 + 'Signature', signature_style)
        self.story.append(signature_paragraph)

    def build(self):
        self.document.build(self.story)

def main(file, outputfile):
    data = collection(file)
    pdf_report = PDFReport(outputfile)
    pdf_report.add_invoice_table(data)
    pdf_report.add_signature()
    pdf_report.build()

# Usage
main('bill.txt', 'bill.pdf')
