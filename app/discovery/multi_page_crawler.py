from typing import List

from app.cleaner.html_cleaner import HTMLCleaner
from app.discovery.link_discovery import LinkDiscovery
from app.discovery.page_prioritizer import PagePrioritizer
from app.scraper.playwright_scraper import PlaywrightScraper


class MultiPageCrawler:
    """
    Crawls the most important pages of a company website
    and merges their cleaned content into one document.
    """

    def __init__(self):

        self.scraper = PlaywrightScraper()
        self.cleaner = HTMLCleaner()
        self.discovery = LinkDiscovery()
        self.prioritizer = PagePrioritizer()

    def crawl(
        self,
        homepage_url: str,
        max_pages: int = 12,
    ) -> str:

        print("\n==========================================")
        print("Starting Multi-Page Crawl")
        print("==========================================\n")

        # Step 1: Scrape homepage
        print(f"Scraping Homepage: {homepage_url}")

        homepage_html = self.scraper.scrape(homepage_url)

        if not homepage_html:

            print("Failed to scrape homepage.")

            self.scraper.close_browser()

            return ""

        # Step 2: Discover internal links
        discovered = self.discovery.discover(
            homepage_html,
            homepage_url,
        )

        print(f"Discovered {len(discovered)} internal pages.")

        # Step 3: Prioritize pages
        prioritized = self.prioritizer.prioritize(discovered)

        merged_content: List[str] = []

        # Add cleaned homepage first
        merged_content.append(
            self.cleaner.clean(homepage_html)
        )

        visited = set()

        print("\nCrawling Important Pages:\n")

        # Step 4: Crawl top priority pages
        for page in prioritized:

            if len(visited) >= max_pages:
                break

            page_url = str(page.url)

            # Skip homepage
            if page_url == homepage_url:
                continue

            # Skip low-priority pages
            if page.score <= 0:
                continue

            # Skip duplicates
            if page_url in visited:
                continue

            print(f"[Score: {page.score}] {page.text} -> {page_url}")

            html = self.scraper.scrape(page_url)

            if not html:
                print("  Failed")
                continue

            cleaned = self.cleaner.clean(html)

            merged_content.append(cleaned)

            visited.add(page_url)

        self.scraper.close_browser()

        final_document = "\n\n".join(merged_content)

        print("\n==========================================")
        print("Multi-Page Crawl Completed")
        print(f"Pages Crawled : {len(visited) + 1}")
        print(f"Document Size : {len(final_document):,} characters")
        print("==========================================\n")

        return final_document