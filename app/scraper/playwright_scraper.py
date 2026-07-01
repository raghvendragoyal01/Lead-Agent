from typing import Optional

from playwright.sync_api import (
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

from app.utils.logger import get_logger

logger = get_logger(__name__)


class PlaywrightScraper:
    """
    Downloads fully rendered HTML from company websites.
    """

    def __init__(self, headless: bool = True):

        self.headless = headless

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def launch_browser(self):

        logger.info("Launching Playwright browser...")

        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        self.context = self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
            viewport={
                "width": 1366,
                "height": 768,
            },
        )

        self.page = self.context.new_page()

        logger.info("Browser launched successfully.")

    def scrape(
        self,
        url: str,
        timeout: int = 60000,
    ):

        try:

            if self.page is None:
                self.launch_browser()

            logger.info(f"Scraping: {url}")

            # Navigate to the page
            self.page.goto(
                url,
                timeout=timeout,
                wait_until="domcontentloaded",
            )

            # Allow JavaScript to finish rendering
            self.page.wait_for_timeout(3000)

            # Scroll once to trigger lazy-loaded content
            self.page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )

            self.page.wait_for_timeout(2000)

            html = self.page.content()

            logger.info(
                f"Successfully scraped ({len(html):,} characters)."
            )

            return html

        except PlaywrightTimeoutError:

            logger.error(
                f"Timeout while scraping: {url}"
            )

            return None

        except PlaywrightError as e:

            logger.error(
                f"Playwright error while scraping {url}: {e}"
            )

            return None

        except Exception as e:

            logger.exception(
                f"Unexpected error while scraping {url}: {e}"
            )

            return None

    def close_browser(self):

        logger.info("Closing Playwright browser...")

        try:

            if self.page:
                self.page.close()

            if self.context:
                self.context.close()

            if self.browser:
                self.browser.close()

            if self.playwright:
                self.playwright.stop()

            logger.info("Browser closed successfully.")

        except Exception as e:

            logger.exception(
                f"Error while closing browser: {e}"
            )