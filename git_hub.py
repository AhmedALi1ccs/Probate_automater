import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import time

st.title("Probate Auto Bot")
business_day = st.date_input("Select Auction Date")
run_button = st.button("Run Scraper")

# Initialize an empty DataFrame for collected data
data = pd.DataFrame()

# Scraping function using Playwright
def scraper(business_day):
    formatted_date = business_day.strftime('%Y%m%d')
    url = f"https://probatesearch.franklincountyohio.gov/netdata/PBODateInx.ndm/input?string={formatted_date}"

    # Start Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Run in headless mode for deployment
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)

        all_data = []

        # Locate rows in the table
        try:
            rows = page.locator("//tr[@bgcolor='lightblue' or @bgcolor='White']")
            row_count = rows.count()

            print(f"Processing BusinessDay: {business_day}, Rows found: {row_count}")

            for row_index in range(row_count):
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

                    # Scrape the details from the case page
                    case_details = {}
                    detail_rows = page.locator("//table[@bgcolor='lightblue']/tbody/tr")
                    for detail_row in detail_rows.element_handles():
                        try:
                            header = detail_row.query_selector("th").text_content().strip()
                            value = detail_row.query_selector("td").text_content().strip()

                            # Rename specific columns to avoid conflicts
                            if header == "City":
                                header = "Property City"
                            elif header == "State":
                                header = "Property State"
                            elif header == "Zip":
                                header = "Property Zip"

                            case_details[header] = value
                        except Exception:
                            continue

                    # Fetch the `caseno` from the case details
                    case_number = case_details.get("Case Number / Suffix", "").strip()
                    if not case_number:
                        print("No case number found. Skipping.")
                        page.go_back()
                        continue

                    # Generate the new URL with the fetched `caseno`
                    additional_url = f"https://probatesearch.franklincountyohio.gov/netdata/PBFidDetail.ndm/FID_DETAIL?caseno={case_number};;01"
                    page.goto(additional_url)

                    # Wait for the additional page to load
                    page.wait_for_selector("//table[@bgcolor='lightblue']")

                    # Scrape the additional details
                    additional_details = {}
                    additional_rows = page.locator("//table[@bgcolor='lightblue']/tbody/tr")
                    for add_row in additional_rows.element_handles():
                        try:
                            header = add_row.query_selector("th").text_content().strip()
                            value = add_row.query_selector("td").text_content().strip()
                            additional_details[header] = value
                        except Exception:
                            continue

                    # Merge case details and additional details
                    combined_data = {**case_details, **additional_details}
                    all_data.append(combined_data)

                    # Go back to the main page
                    page.goto(url)
        finally:
            browser.close()
        return pd.DataFrame(all_data)

# Save the data to a CSV file
if run_button:
    st.info("Starting the scraping process...")
    data = scraper(business_day)
    if not data.empty:
        # Process data
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
            label="Download CSV",
            data=data.to_csv(index=False).encode('utf-8'),
            file_name=f'Probate{business_day.strftime("%Y%m%d")}.csv',
            mime='text/csv'
        )

        print("Data saved to case_and_fiduciary_details.csv")
else:
    print("No data extracted.")
