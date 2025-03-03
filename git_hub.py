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

                        # Get additional details from the FID_DETAIL page
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

                        # NEW CODE: Visit the attorney details page to get attorney information
                        attorney_url = f"https://probatesearch.franklincountyohio.gov/netdata/PBAttyDetail.ndm/ATTY_DETAIL?caseno={case_number};;01"
                        page.goto(attorney_url)
                        
                        # Wait for the attorney details table to load
                        attorney_details = {}
                        try:
                            page.wait_for_selector("//table[@bgcolor='lightblue']", timeout=20000)
                            attorney_rows = page.locator("//table[@bgcolor='lightblue']/tbody/tr")
                            
                            # Process each row in the attorney details table
                            for atty_row in attorney_rows.element_handles():
                                try:
                                    header_element = atty_row.query_selector("th")
                                    value_element = atty_row.query_selector("td")
                                    
                                    if header_element and value_element:
                                        header = header_element.text_content().strip()
                                        value = value_element.text_content().strip()
                                        
                                        # Skip rows with buttons or links
                                        if "Back" in value or "View" in value or "New Search" in value or "Homepage" in value:
                                            continue
                                            
                                        # Add "Attorney_" prefix to all attorney detail fields
                                        attorney_details[f"Attorney_{header}"] = value
                                except Exception:
                                    continue
                        except Exception as e:
                            st.warning(f"Error processing attorney data for case {case_number}: {e}")

                        # Visit the fiduciary page to get more information
                        fiduciary_url = f"https://probatesearch.franklincountyohio.gov/netdata/PBFidy.ndm/input?caseno={case_number};;"
                        page.goto(fiduciary_url)
                        
                        # Wait for the fiduciary table to load
                        fiduciary_info = {}
                        try:
                            page.wait_for_selector("table[border='1'][align='center'][cellpadding='1'][bgcolor='black']", timeout=20000)
                            fiduciary_table = page.locator("table[border='1'][align='center'][cellpadding='1'][bgcolor='black']")
                            
                            # Get all rows except header and footer
                            fiduciary_rows = fiduciary_table.locator("tr[bgcolor='lightblue']")
                            
                            # Extract fiduciary information
                            for i in range(fiduciary_rows.count()):
                                row = fiduciary_rows.nth(i)
                                cells = row.locator("td")
                                
                                # Extract relevant information
                                fiduciary_number = cells.nth(0).inner_text().strip()
                                fiduciary_name = cells.nth(1).inner_text().strip()
                                title = cells.nth(2).inner_text().strip()
                                title_description = cells.nth(3).inner_text().strip()
                                appt_date = cells.nth(4).inner_text().strip()
                                term_date = cells.nth(5).inner_text().strip()
                                case_closed_date = cells.nth(6).inner_text().strip()
                                attorney_number = cells.nth(7).inner_text().strip()
                                attorney_name = cells.nth(8).inner_text().strip()
                                
                                # Add these to fiduciary_info
                                fiduciary_info[f"Fiduciary_{i+1}_Number"] = fiduciary_number
                                fiduciary_info[f"Fiduciary_{i+1}_Name"] = fiduciary_name
                                fiduciary_info[f"Fiduciary_{i+1}_Title"] = title
                                fiduciary_info[f"Fiduciary_{i+1}_Title_Description"] = title_description
                                fiduciary_info[f"Fiduciary_{i+1}_Appointment_Date"] = appt_date
                                fiduciary_info[f"Fiduciary_{i+1}_Term_Date"] = term_date
                                fiduciary_info[f"Fiduciary_{i+1}_Case_Closed_Date"] = case_closed_date
                                fiduciary_info[f"Fiduciary_{i+1}_Attorney_Number"] = attorney_number
                                fiduciary_info[f"Fiduciary_{i+1}_Attorney_Name"] = attorney_name
                            
                        except Exception as e:
                            st.warning(f"Error processing fiduciary data for case {case_number}: {e}")
                            fiduciary_info = {}

                        # Combine all the data
                        combined_data = {**case_details, **additional_details, **attorney_details, **fiduciary_info}
                        data.append(combined_data)

                        # Go back to the main page
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
        try:
            data = Scrapper(business_day)
            
            if not data.empty:
                try:
                    # Debug information
                    st.write("Sample of Estate Fiduciaries Names:")
                    if 'Estate Fiduciaries Name' in data.columns:
                        st.write(data['Estate Fiduciaries Name'].head())
                    elif 'Fiduciary_1_Name' in data.columns:
                        st.write(data['Fiduciary_1_Name'].head())
                    
                    # Handle name splitting for the primary fiduciary
                    primary_name_column = None
                    if 'Estate Fiduciaries Name' in data.columns:
                        primary_name_column = 'Estate Fiduciaries Name'
                    elif 'Fiduciary_1_Name' in data.columns:
                        primary_name_column = 'Fiduciary_1_Name'
                    
                    if primary_name_column:
                        split_names = data[primary_name_column].str.split(',', n=1, expand=True)
                        
                        # Safely assign Last Name
                        data['Last Name'] = split_names[0].fillna('')
                        
                        # Safely assign First Name
                        data['First Name'] = ''  # Default empty string
                        if split_names.shape[1] > 1:  # Check if there's a second part
                            data.loc[split_names[1].notna(), 'First Name'] = (
                                split_names[1].str.strip()
                                .str.split()
                                .str[0]
                                .fillna('')
                            )
                    else:
                        st.warning("No primary fiduciary name column found for name splitting")
                    
                    # Column renaming
                    column_mapping = {
                        'Decedent Street': 'Property Address',
                        'Street': 'Mailing Address',
                        'City': 'Mailing City',
                        'State': 'Mailing State',
                        'Zip': 'Mailing zip',
                        'Date Opened': 'Probate Open Date'
                    }
                    
                    # Only rename columns that exist
                    for old_name, new_name in column_mapping.items():
                        if old_name in data.columns:
                            data = data.rename(columns={old_name: new_name})
                     
                    # Include attorney details in the columns to keep
                    attorney_columns = [col for col in data.columns if col.startswith('Attorney_')]
                    
                    columns_to_keep = [
                       'Property Address', 'Property City', 'Property State', 'Property Zip', 
                       'Mailing Address', 'Mailing City', 'Mailing State', 'Mailing zip', 
                       'Phone Number', 'First Name', 'Last Name', 'Probate Open Date',
                       'Case Number / Suffix'  # Added case number for reference
                    ] + attorney_columns
                    
                    # Add fiduciary columns if they exist
                    # fiduciary_columns = [col for col in data.columns if col.startswith('Fiduciary_')]
                    # columns_to_keep += fiduciary_columns
                    
                    # Keep only columns that exist in the data
                    columns_to_keep = [col for col in columns_to_keep if col in data.columns]
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
                
                except KeyError as ke:
                    st.error(f"Error processing data: Column not found - {str(ke)}")
                    st.write("Available columns:", list(data.columns))
                except Exception as e:
                    st.error(f"Error processing data: {str(e)}")
                    st.write("Data shape:", data.shape)
                    st.write("Data columns:", list(data.columns))
            else:
                st.warning("No data was retrieved from the scraper.")
                
        except Exception as e:
            st.error(f"Error during scraping: {str(e)}")
