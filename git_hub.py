import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import time
import subprocess

# Install the Playwright browsers if not already installed
subprocess.run(["playwright", "install", "chromium"], check=True)
# Custom Styling
st.set_page_config(
    page_title="Probate Data Scraper", 
    page_icon="⚖️", 
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .big-font {
        font-size:20px !important;
        color: #4a4a4a;
    }
    .stButton>button {
        color: white;
        background-color: #4CAF50;
        border-radius: 10px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #45a049;
        transform: scale(1.05);
    }
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏛️ Probate Data Scraper")
st.markdown("### Extract Detailed Probate Case Information", unsafe_allow_html=True)

# Sidebar for additional context
business_day = st.date_input("Select Auction Date")
run_button = st.button("Run Scraper")

def Scrapper(business_day):
    formatted_date = business_day.strftime('%Y%m%d')
    url = f"https://probatesearch.franklincountyohio.gov/netdata/PBODateInx.ndm/input?string={formatted_date}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        time.sleep(5) 
        data = []

        try:
            page.wait_for_selector("//tr[@bgcolor='lightblue' or @bgcolor='White']", timeout=30000)
            
            rows = page.locator("//tr[@bgcolor='lightblue' or @bgcolor='White']")
            row_count = rows.count()
            
            progress_bar = st.progress(0)
            status_text = st.empty()

            for row_index in range(row_count):
                try:
                    status_text.info(f"Processing row {row_index+1} of {row_count}")
                    progress_bar.progress((row_index + 1) / row_count)

                    rows = page.locator("//tr[@bgcolor='lightblue' or @bgcolor='White']")
                    row = rows.nth(row_index)

                    type_column = row.locator("td:nth-child(3)")
                    if "ESTATE" in type_column.text_content():
                        case_link = row.locator("a")
                        case_link.click()

                        page.wait_for_selector("//table[@bgcolor='lightblue']", timeout=20000)
                        time.sleep(2)  
                        detail_rows = page.locator("//table[@bgcolor='lightblue']/tbody/tr")

                        case_details = {}
                        for detail_row in detail_rows.element_handles():
                            try:
                                header = detail_row.query_selector("th").text_content().strip()
                                value = detail_row.query_selector("td").text_content().strip()

                                # Column name mapping
                                header_map = {
                                    "City": "Property City",
                                    "State": "Property State", 
                                    "Zip": "Property Zip"
                                }
                                header = header_map.get(header, header)
                                case_details[header] = value
                            except Exception:
                                continue

                        case_number = case_details.get("Case Number / Suffix", "").strip()
                        if not case_number:
                            page.go_back()
                            continue

                        additional_url = f"https://probatesearch.franklincountyohio.gov/netdata/PBFidDetail.ndm/FID_DETAIL?caseno={case_number};;01"
                        page.goto(additional_url)

                        page.wait_for_selector("//table[@bgcolor='lightblue']", timeout=20000)
                        additional_rows = page.locator("//table[@bgcolor='lightblue']/tbody/tr")

                        additional_details = {}
                        for add_row in additional_rows.element_handles():
                            try:
                                header = add_row.query_selector("th").text_content().strip()
                                value = add_row.query_selector("td").text_content().strip()
                                additional_details[header] = value
                            except Exception:
                                continue

                        combined_data = {**case_details, **additional_details}
                        data.append(combined_data)

                        page.goto(url)
                        page.wait_for_selector("//tr[@bgcolor='lightblue' or @bgcolor='White']", timeout=20000)

                except Exception as e:
                    st.warning(f"Error processing row {row_index}: {e}")
                    page.goto(url)
                    continue

        except Exception as e:
            st.error(f"Error during scraping: {e}")
        finally:
            browser.close()

        return pd.DataFrame(data)

if run_button:
    with st.spinner('Scraping in progress...'):
        data = Scrapper(business_day)
    
    # Replace the current name splitting code with this:
    if not data.empty:
        try:
            # First, ensure the column exists
            if 'Estate Fiduciaries Name' not in data.columns:
                st.error("Column 'Estate Fiduciaries Name' not found in the data")
            else:
                # Handle name splitting with error checking
                split_names = data['Estate Fiduciaries Name'].str.split(',', n=1, expand=True)
                
                # Safely assign Last Name
                data['Last Name'] = split_names[0].fillna('')
                
                # Safely assign First Name
                data['First Name'] = ''  # Default empty string
                mask = split_names.shape[1] > 1  # Check if there's a second part
                if mask:
                    data.loc[split_names[1].notna(), 'First Name'] = (
                        split_names[1].str.strip()
                        .str.split()
                        .str[0]
                        .fillna('')
                    )
    
            # Rest of your code remains the same
            data = data.rename(columns={
                'Decedent Street': 'Property Address',
                'Street': 'Mailing Address',
                'City': 'Mailing City',
                'State': 'Mailing State',
                'Zip': 'Mailing zip',
                'Date Opened': 'Probate Open Date'
            })
        
        columns_to_keep = [
            'Property Address', 'Property City', 'Property State', 'Property Zip', 
            'Mailing Address', 'Mailing City', 'Mailing State', 'Mailing zip', 
            'Phone Number', 'First Name', 'Last Name', 'Probate Open Date'
        ]
        data = data[columns_to_keep]
        
        

        st.success(f"✅ Scraping completed! Total entries: {len(data)}")
        st.dataframe(data, use_container_width=True)
        
        st.download_button(
            label="Download CSV 📄",
            data=data.to_csv(index=False).encode('utf-8'),
            file_name=f'probate_details_{business_day.strftime("%Y%m%d")}.csv',
            mime='text/csv',
            key='download_btn'
        )
