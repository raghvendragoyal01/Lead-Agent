from app.scraper.playwright_scraper import PlaywrightScraper


def show_context(html: str, keyword: str):

    lower = html.lower()

    idx = lower.find(keyword)

    if idx == -1:
        print(f"{keyword}: NOT FOUND\n")
        return

    start = max(0, idx - 250)
    end = min(len(html), idx + 350)

    print(f"\n========== {keyword.upper()} ==========\n")
    print(html[start:end])
    print("\n")


def main():

    scraper = PlaywrightScraper()

    html = scraper.scrape("https://www.apollohospitals.com/")

    scraper.close_browser()

    for keyword in [
        "facebook",
        "twitter",
        "youtube",
        "linkedin",
    ]:
        show_context(html, keyword)


if __name__ == "__main__":
    main()