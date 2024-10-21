import datetime
import pandas as pd
from fpdf import FPDF

# Set font size and cell height
S = 10  # Font size
H = 6   # Cell height
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
    scale = 190/sum(col_widths)
    col_widths = [ i*scale for i in col_widths ]
    return col_widths

# Function to print the table headers
def print_table_header(pdf, col_widths, header, S, H, B):
    pdf.set_font('Arial', '', S)
    for i, col_name in enumerate(header):
        pdf.cell(col_widths[i], H, col_name, border=B, align='L')
    pdf.ln()

# Function to print the table
def print_table(pdf,df,border = 0,print_header = True) : 
    B = border
    pdf.set_font('Arial', '', S)
    col_widths = calculate_col_widths(df, pdf)
    header = df.columns.tolist()
    if print_header:  print_table_header(pdf, col_widths, header, S, H, B)

    # Print DataFrame rows and repeat header on each new page if needed
    for index, row in df.iterrows():
        # Check if a new page is needed
        if pdf.get_y() > 280 :  # Adjust this value if you need more/less space before the footer
            pdf.add_page()      # Add a new page
            print_table_header(pdf, col_widths, header, S, H, B)  # Reprint the header on the new page

        for i, item in enumerate(row):
                pdf.cell(col_widths[i], H, str(item), border=B, align='L')
        pdf.ln()

def create_pdf(tables:tuple[pd.DataFrame],header = False,salesman = None) : 
    # Load and process the data

    df,party_sales = tables 
    df = df.dropna(subset="Sr No")
    df["MRP"] = df["MRP"].str.split(".").str[0]
    df["LC"] = df["Total LC.Units"].str.split(".").str[0]
    df["Units"] = df["Total LC.Units"].str.split(".").str[1]
    df = df.rename(columns={"Total FC": "FC", "Total Gross Sales": "Gross Value"})
    df = df[["Product Name", "MRP", "FC", "Units", "LC","UPC", "Gross Value"]]
    df = df.fillna("")
    
    df[["FC","LC"]] = df[["FC","LC"]].replace({"0" : "-"})
    total_fc = df["FC"].iloc[-1]
    total_lc = df["LC"].iloc[-1]
    df = df.iloc[:-1]

    party_sales = party_sales.dropna(subset="Party")
    party_sales = party_sales[["Bill No","Party","Gross Amount","Sch.Disc","Cash.Disc","Net Amt"]]
    party_sales = party_sales.fillna("")

    no_of_bills = len(party_sales.index) - 1 
    outlet_count = party_sales["Party"].nunique() - 1
    # bills =  f'{party_sales["Party"].min()} - {party_sales["Party"].max()}'
    time = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p") 
    total_value = round(float(party_sales.iloc[-1]["Net Amt"]))
    

    # Create PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=5)
    pdf.add_page()
    pdf.set_font('Arial', '', 10) #,"PARTIES",outlet_count
    header_table = [] 
    if header : header_table.append(["SALESMAN",salesman,"","","VALUE",total_value])
    header_table.append(["TIME",time,"","","BILLS",no_of_bills])
    header_table.append(["TOTAL LC",total_lc,"","","TOTAL FC",total_fc])
    header_table = pd.DataFrame(header_table,dtype="str",columns=["a","b","c","d","e","f"])
    print_table(pdf,header_table,border=0,print_header=False)
    pdf.ln(5)

    print_table(pdf,df)
    if header : 
        pdf.ln(5)
        print_table(pdf,party_sales,border = 1)
        
    # Output the PDF
    pdf.output(OUTPUT_PDF_FILE)

    print(f"PDF generated: {OUTPUT_PDF_FILE}")
