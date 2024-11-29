import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import time
import os
def install_browsers():
    p = sync_playwright().start()
    p.chromium.install()
    p.stop()

# Install Playwright browsers (required for deployment)
install_browsers()


st.title("Probate Auto Bot")

# User Input for Date
business_day = st.date_input("Select Auction Date")
run_button = st.button("Run Scraper")

# Scraper Function
def scraper(business_day):
    """Scrape probate data for the selected business day."""
    formatted_date = business_day.strftime('%Y%m%d')
    url = f"https://probatesearch.franklincountyohio.gov/netdata/PBODateInx.ndm/input?string={formatted_date}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)

        all_data = []

        try:
            # Wait for the table rows to load
            page.wait_for_selector("//tr[@bgcolor='lightblue' or @bgcolor='White']", timeout=15000)
            rows = page.locator("//tr[@bgcolor='lightblue' or @bgcolor='White']")
            row_count = rows.count()

            if row_count == 0:
                st.warning("No rows found for the selected date.")
                return pd.DataFrame()

            for row_index in range(row_count):
                try:
                    # Refresh rows dynamically
                    rows = page.locator("//tr[@bgcolor='lightblue' or @bgcolor='White']")
                    row = rows.nth(row_index)

                    # Check if the Type column contains "ESTATE"
                    type_column = row.locator("td:nth-child(3)")
                    if "ESTATE" in type_column.text_content():
                        # Click the case link
                        case_link = row.locator("a")
                        case_link.click()

                        # Wait for the case detail page to load
                        page.wait_for_selector("//table[@bgcolor='lightblue']")
                        detail_rows = page.locator("//table[@bgcolor='lightblue']/tbody/tr")

                        # Extract details
                        case_details = {}
                        for detail_row in detail_rows.element_handles():
                            try:
                                header = detail_row.query_selector("th").text_content().strip()
                                value = detail_row.query_selector("td").text_content().strip()
                                case_details[header] = value
                            except Exception:
                                continue

                        # Fetch additional details using the `caseno`
                        case_number = case_details.get("Case Number / Suffix", "").strip()
                        if case_number:
                            additional_url = f"https://probatesearch.franklincountyohio.gov/netdata/PBFidDetail.ndm/FID_DETAIL?caseno={case_number};;01"
                            page.goto(additional_url)
                            page.wait_for_selector("//table[@bgcolor='lightblue']")
                            additional_rows = page.locator("//table[@bgcolor='lightblue']/tbody/tr")

                            for add_row in additional_rows.element_handles():
                                try:
                                    header = add_row.query_selector("th").text_content().strip()
                                    value = add_row.query_selector("td").text_content().strip()
                                    case_details[header] = value
                                except Exception:
                                    continue

                        # Append data
                        all_data.append(case_details)

                        # Return to the main page
                        page.goto(url)
                        page.wait_for_selector("//tr[@bgcolor='lightblue' or @bgcolor='White']")
                except Exception as e:
                    st.warning(f"Error processing row {row_index + 1}: {e}")
                    continue

        except Exception as e:
            st.error(f"Error during scraping: {e}")
        finally:
            browser.close()

        return pd.DataFrame(all_data)

# Run Scraper
if run_button:
    st.info("Starting the scraping process...")
    data = scraper(business_day)

    if not data.empty:
        # Process and Display Data
        st.success(f"✅ Scraping completed! Total entries: {len(data)}")
        st.dataframe(data)

        # Download Button
        st.download_button(
            label="Download CSV",
            data=data.to_csv(index=False).encode('utf-8'),
            file_name=f'ProbateDetails_{business_day.strftime("%Y%m%d")}.csv',
            mime='text/csv'
        )
    else:
        st.warning("No data available for the selected date.")
