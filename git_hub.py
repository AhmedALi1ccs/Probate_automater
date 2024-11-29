import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import os
import logging

# Install Playwright browsers at runtime
os.system("playwright install chromium")

# Logging for debugging purposes
logging.basicConfig(level=logging.INFO)

st.title("Probate Auto Bot")

# User Input for Date
business_day = st.date_input("Select Auction Date")
run_button = st.button("Run Scraper")

# Scraper Function
def scraper(business_day):
    formatted_date = business_day.strftime('%Y%m%d')
    url = f"https://probatesearch.franklincountyohio.gov/netdata/PBODateInx.ndm/input?string={formatted_date}"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto(url)
            
            # Wait for the rows to load
            page.wait_for_selector("//tr[@bgcolor='lightblue' or @bgcolor='White']", timeout=15000)
            rows = page.locator("//tr[@bgcolor='lightblue' or @bgcolor='White']")
            row_count = rows.count()

            if row_count == 0:
                st.warning("No rows found for the selected date.")
                return pd.DataFrame()

            all_data = []
            for i in range(row_count):
                try:
                    row = rows.nth(i)
                    case_link = row.locator("a")
                    case_link.click()
                    page.wait_for_selector("//table[@bgcolor='lightblue']")
                    case_data = {}
                    rows = page.locator("//table[@bgcolor='lightblue']/tbody/tr")
                    for detail_row in rows.element_handles():
                        try:
                            key = detail_row.query_selector("th").text_content().strip()
                            value = detail_row.query_selector("td").text_content().strip()
                            case_data[key] = value
                        except Exception:
                            continue
                    all_data.append(case_data)
                    page.go_back()
                except Exception as e:
                    logging.warning(f"Error processing row {i + 1}: {e}")
                    continue

            return pd.DataFrame(all_data)
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
        st.error("Scraping failed. Check logs for details.")
        return pd.DataFrame()

# Run Scraper
if run_button:
    st.info("Starting the scraping process...")
    data = scraper(business_day)
    if not data.empty:
        st.success(f"✅ Scraping completed! Total entries: {len(data)}")
        st.dataframe(data)
        st.download_button(
            label="Download CSV",
            data=data.to_csv(index=False).encode('utf-8'),
            file_name=f'ProbateDetails_{business_day.strftime("%Y%m%d")}.csv',
            mime='text/csv'
        )
    else:
        st.warning("No data available for the selected date.")
