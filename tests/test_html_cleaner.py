from app.scraper.playwright_scraper import PlaywrightScraper
from app.cleaner.html_cleaner import HTMLCleaner


def main():

    scraper = PlaywrightScraper()

    cleaner = HTMLCleaner()

    url = "https://www.apollohospitals.com/"

    html = scraper.scrape(url)

    if not html:
        print("Scraping Failed")
        return

    cleaned = cleaner.clean(html)

    print("\nRaw HTML Length:", len(html))

    print("Cleaned Text Length:", len(cleaned))

    print("\nPreview:\n")

    print(cleaned[:3000])

    scraper.close_browser()


if __name__ == "__main__":
    main()