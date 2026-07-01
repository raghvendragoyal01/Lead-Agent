from app.scraper.playwright_scraper import PlaywrightScraper


def main():

    scraper = PlaywrightScraper(headless=True)

    url = "https://www.apollohospitals.com/"

    print(f"\nScraping: {url}\n")

    html = scraper.scrape(url)

    if html:

        print("✅ HTML Download Successful\n")

        print(f"HTML Length: {len(html)}\n")

        print("First 1000 Characters:\n")

        print(html[:1000])

    else:

        print("❌ Failed to scrape website.")

    scraper.close_browser()


if __name__ == "__main__":
    main()