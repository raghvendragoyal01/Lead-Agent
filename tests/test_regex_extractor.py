from app.scraper.playwright_scraper import PlaywrightScraper
from app.cleaner.html_cleaner import HTMLCleaner
from app.extractor.regex_extractor import RegexExtractor


def main():

    scraper = PlaywrightScraper()

    cleaner = HTMLCleaner()

    extractor = RegexExtractor()

    html = scraper.scrape(
        "https://www.apollohospitals.com/"
    )

    cleaned = cleaner.clean(html)

    emails = extractor.extract_emails(cleaned)

    phones = extractor.extract_phones(cleaned)

    print("\nEMAILS\n")

    for email in emails:
        print(email)

    print("\nPHONES\n")

    for phone in phones:
        print(phone)

    scraper.close_browser()


if __name__ == "__main__":
    main()