import datetime
import pandas as pd
from fpdf import FPDF

# Set font size and cell height
S = 10  # Font size
H = 6   # Cell height
OUTPUT_PDF_FILE = "loading.pdf"

class PDF(FPDF):
    def header(self):
        # Call the parent header method if you want to keep default behavior
        super().header()

        # Move to the top right corner
        self.set_y(10)  # Adjust vertical position as needed
        # self.set_x(self.w - 30)  # Right margin minus padding
        
        # Print the page number on the right
        self.cell(0, 10, f'{datetime.date.today().strftime("%d-%m-%Y")}', 0, 0, 'L')
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'R')
        self.ln(10)

# Function to calculate the column widths based on content
def calculate_col_widths(df, pdf):
    col_widths = []
    for col in df.columns:
        max_width = pdf.get_string_width(col) + 4  # Start with the header width
        for value in df[col]:
            value_width = pdf.get_string_width(str(value).replace(' ','X')) + 4
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

from enum import Enum 
LoadingSheetType = Enum("LoadingSheetType","Salesman Plain")

def create_pdf(tables:tuple[pd.DataFrame],sheet_type:LoadingSheetType,context = {}) : 
    # Load and process the data

    df,party_sales = tables 
    df = df.dropna(subset="Sr No")
    df["MRP"] = df["MRP"].str.split(".").str[0]
    df["LC"] = df["Total LC.Units"].str.split(".").str[0]
    df["Units"] = df["Total LC.Units"].str.split(".").str[1]
    df = df.rename(columns={"Total FC": "FC", "Total Gross Sales": "Gross Value"})

    total_fc = df["FC"].iloc[-1]
    total_lc = df["LC"].iloc[-1]
    df = df.fillna("")
    df["No"] = df.index.copy() +  1    
    df[["FC","LC"]] = df[["FC","LC"]].replace({"0" : ""})
    df = df.iloc[:-1]
    df = df[["No","Product Name", "MRP", "FC", "Units", "LC","UPC", "Gross Value","Division Name"]]

    party_sales = party_sales.dropna(subset="Party")
    party_sales = party_sales.sort_values("Bill No")
    party_sales = party_sales.fillna("")
    party_sales["No"] = party_sales.reset_index(drop=True).index.copy() +  1    
    party_sales = party_sales[["No","Bill No","Party","Gross Amount","Sch.Disc","Net Amt"]]
    

    no_of_bills = len(party_sales.index) - 1 
    outlet_count = party_sales["Party"].nunique() - 1
    lines_count = len(df.index)
    # bills =  f'{party_sales["Party"].min()} - {party_sales["Party"].max()}'
    time = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p") 
    total_value = round(float(party_sales.iloc[-1]["Net Amt"]))
    

    # Create PDF
    pdf = PDF()
    pdf.set_top_margin(15)
    pdf.set_auto_page_break(auto=True, margin=5)
    pdf.set_font('Arial', '', 10)
    pdf.add_page()
    header_table = []

    if sheet_type == LoadingSheetType.Salesman :
        header_table.append(["TIME",time,"","","VALUE",total_value])
        header_table.append(["SALESMAN",context["salesman"] ,"","","BEAT",context["beat"]])
        header_table.append(["PARTY",(context["party"] or "SALESMAN").ljust(34).upper(),"","","TOTAL CASE",total_fc])
        header_table.append(["BILL",context["inum"],"","","",""])
        df["Case"] = (df["FC"].apply(lambda x: int(x) if x else 0) + df["LC"].apply(lambda x: int(x) if x else 0)).astype(str).replace("0","")
        dfs = df[["No","Product Name","MRP","Case","Units","UPC","Gross Value"]]
        dfs.loc[len(dfs.index)] = ["","Total"] + [""] * 4 + [total_value]
        
    if sheet_type == LoadingSheetType.Plain :
        header_table.append(["TIME",time,"","","BILLS",no_of_bills])
        header_table.append(["LINES",lines_count,"","","OUTLETS",outlet_count])
        header_table.append(["TOTAL LC",total_lc,"","","TOTAL FC",total_fc])
        df[["LC.","Units.","FC."]] = df[["LC","Units","FC"]].copy()
        df['group'] = (df['Division Name'] != "").cumsum()
        split_dfs = [group for _, group in df.groupby('group') if (group['Division Name'] != "").any()]
        dfs = [group[["No","Product Name","MRP","LC","Units","FC","UPC","LC.","Units.","FC."]] for group in split_dfs]


    header_table = pd.DataFrame(header_table,dtype="str",columns=["a","b","c","d","e","f"])
    print_table(pdf,header_table,border=0,print_header=False)
    pdf.ln(5)
    if type(dfs) == pd.DataFrame : dfs = [dfs,]
    for index,df in enumerate(dfs) :
        print_table(pdf,df,border=1)
        if index < len(dfs) -1 : 
            pdf.ln(25)

    if sheet_type == LoadingSheetType.Plain : 
        pdf.add_page()
    if sheet_type == LoadingSheetType.Salesman : 
        pdf.ln(5)

    print_table(pdf,party_sales,border = 1)
        
    # Output the PDF
    pdf.output(OUTPUT_PDF_FILE)

    print(f"PDF generated: {OUTPUT_PDF_FILE}")
