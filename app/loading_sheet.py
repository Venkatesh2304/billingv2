import datetime
import pandas as pd
from fpdf import FPDF

# Set font size and cell height
S = 10  # Font size
H = 6   # Cell height
B = 0   # Border (0 for no border)
OUTPUT_PDF_FILE = "loading.pdf"

# Function to calculate the column widths based on content
def calculate_col_widths(df, pdf):
    col_widths = []
    for col in df.columns:
        max_width = pdf.get_string_width(col) + 4  # Start with the header width
        for value in df[col]:
            value_width = pdf.get_string_width(str(value)) + 4
            max_width = max(max_width, value_width)
        col_widths.append(max_width)
    return col_widths

# Function to print the table headers
def print_table_header(pdf, col_widths, header, S, H, B):
    pdf.set_font('Arial', '', S)
    for i, col_name in enumerate(header):
        pdf.cell(col_widths[i], H, col_name, border=B, align='L'  if i == 0 else 'C')
    pdf.ln()

def create_pdf(df,header = False,salesman = None) : 
    # Load and process the data
    # df = df.iloc[:-1]
    df = df.dropna(subset="Sr No")
    df["MRP"] = df["MRP"].str.split(".").str[0]
    df["LC"] = df["Total LC.Units"].str.split(".").str[0]
    df["Units"] = df["Total LC.Units"].str.split(".").str[1]
    df = df.rename(columns={"Total FC": "FC", "Total Gross Sales": "Gross Value"})
    df = df[["Product Name", "MRP", "FC", "Units", "LC","UPC", "Gross Value"]]
    df = df.fillna("")
    df[["FC","LC"]] = df[["FC","LC"]].replace({"0" : "-"})
    df.loc[len(df.index)-1,"Product Name"] = "Grand Total"

    # Create PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=5)
    pdf.add_page()
    if header : 
        pdf.set_font('Arial', '', 10)
        pdf.cell(100, 10, f"SALESMAN: {salesman}", ln=0, align='L')  # Salesman name on the left
        pdf.cell(0, 10, f'{datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")}', ln=0, align='R')    
        pdf.ln(5) 
        pdf.cell(0, 10, f"VALUE       : {round(float(df.iloc[-1]['Gross Value']))}", ln=1, align='L')  # Salesman name on the left

    pdf.set_font('Arial', '', S)
    # Calculate column widths
    col_widths = calculate_col_widths(df, pdf)

    # Add a header row
    header = df.columns.tolist()

    # Print header for the first page
    print_table_header(pdf, col_widths, header, S, H, B)

    # Print DataFrame rows and repeat header on each new page if needed
    for index, row in df.iterrows():
        # Check if a new page is needed
        if pdf.get_y() > 300 :  # Adjust this value if you need more/less space before the footer
            pdf.add_page()      # Add a new page
            print_table_header(pdf, col_widths, header, S, H, B)  # Reprint the header on the new page

        for i, item in enumerate(row):
            # Align Product Name to the left, others centered
            if i == 0:  # First column (Product Name) to be left aligned
                pdf.cell(col_widths[i], H, str(item), border=B, align='L')
            else:
                pdf.cell(col_widths[i], H, str(item), border=B, align='C')
        pdf.ln()

    # Output the PDF
    pdf.output(OUTPUT_PDF_FILE)

    print(f"PDF generated: {OUTPUT_PDF_FILE}")

# df = pd.read_excel("a.xlsx", dtype="str")
# create_pdf(df)