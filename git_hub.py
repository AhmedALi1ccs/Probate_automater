import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import time
st.set_page_config(
    page_title="Probate Data Scraper", 
    page_icon="⚖️", 
    layout="wide"
)

st.title("🏛️ Probate Data Scraper")
st.markdown("### Extract Detailed Probate Case Information", unsafe_allow_html=True)
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

        data = []

        try:
            # Increase wait time and add more robust loading check
            page.wait_for_selector("//tr[@bgcolor='lightblue' or @bgcolor='White']", timeout=30000)
            
            # Scroll and wait to ensure all content is loaded
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
            progress_bar = st.progress(0)
            status_text = st.empty()

            rows = page.locator("//tr[@bgcolor='lightblue' or @bgcolor='White']")
            row_count = rows.count()
            st.info(f"Total rows found: {row_count}")

            for row_index in range(row_count):
                try:
                    # Re-locate rows to ensure freshness
                    rows = page.locator("//tr[@bgcolor='lightblue' or @bgcolor='White']")
                    row = rows.nth(row_index)

                    type_column = row.locator("td:nth-child(3)")
                    if "ESTATE" in type_column.text_content():
                        case_link = row.locator("a")
                        case_link.click()

                        # Increased wait time and added network idle
                        page.wait_for_selector("//table[@bgcolor='lightblue']", timeout=20000)
                        page.wait_for_load_state('networkidle')

                        detail_rows = page.locator("//table[@bgcolor='lightblue']/tbody/tr")

                        case_details = {}
                        for detail_row in detail_rows.element_handles():
                            try:
                                header = detail_row.query_selector("th").text_content().strip()
                                value = detail_row.query_selector("td").text_content().strip()

                                if header == "City":
                                    header = "Property City"
                                elif header == "State":
                                    header = "Property State"
                                elif header == "Zip":
                                    header = "Property Zip"

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
                        page.wait_for_load_state('networkidle')

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
    st.info("Starting the scraping process...")
    
    data = Scrapper(business_day)
    if not data.empty:
        split_names = data['Estate Fiduciaries Name'].str.split(', ', n=2, expand=True)
        data['Last Name'] = split_names[0]
        data['First Name'] = split_names[1].str.split(' ').str[0].fillna('')
            
        data = data.rename(columns={'Decedent Street': 'Property Address',
                                "Street":"Mailing Address",
                                "City":"Mailing City",
                                "State":"Mailing State",
                                "Zip":"Mailing zip",
                                "Date Opened":"Probate Open Date"})
        columns_to_keep = ['Property Address',"Property City","Property State","Property Zip","Mailing Address","Mailing City","Mailing State","Mailing zip","Phone Number","First Name","Last Name","Probate Open Date"]
        data = data[columns_to_keep]
        st.success(f"✅ Scraping completed! Total entries: {len(data)}")
        st.dataframe(data)
        st.download_button(
            label="Download CSV 📄",
            data=data.to_csv(index=False).encode('utf-8'),
            file_name=f'auction_details_{business_day.strftime("%Y%m%d")}.csv',
            mime='text/csv'
        )
