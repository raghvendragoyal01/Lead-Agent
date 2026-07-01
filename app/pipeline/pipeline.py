from app.discovery.multi_page_crawler import MultiPageCrawler
from app.extractor.extractor import Extractor
from app.schemas.lead_schema import Lead
from app.utils.logger import get_logger
from app.validator.lead_validator import LeadValidator

logger = get_logger(__name__)


class LeadDiscoveryPipeline:
    """
    Orchestrates the complete Lead Discovery Engine.

    Pipeline:

    Website
        ↓
    Multi Page Crawler
        ↓
    Extractor
        ↓
    Validator
        ↓
    Lead Object
    """

    def __init__(self):

        self.crawler = MultiPageCrawler()
        self.extractor = Extractor()
        self.validator = LeadValidator()

    def run(
        self,
        homepage_url: str,
    ) -> Lead:

        logger.info("==========================================")
        logger.info("Lead Discovery Pipeline Started")
        logger.info("==========================================")

        # Step 1: Crawl the website
        merged_text = self.crawler.crawl(
            homepage_url=homepage_url
        )

        if not merged_text:
            raise RuntimeError(
                "Website crawling failed."
            )

        logger.info("Website Crawling Completed.")

        # Step 2: Extract structured information
        lead = self.extractor.extract(
            text=merged_text,
            website=homepage_url,
        )

        # Step 3: Validate and clean extracted data
        lead = self.validator.validate(
            lead=lead,
            source_text=merged_text,
        )

        logger.info("Lead Extraction Completed.")

        logger.info("==========================================")
        logger.info("Pipeline Finished Successfully")
        logger.info("==========================================")

        return lead