from app.discovery.multi_page_crawler import MultiPageCrawler


def main():

    crawler = MultiPageCrawler()

    text = crawler.crawl(
        "https://www.apollohospitals.com/",
        max_pages=5,
    )

    print("\nMerged Text Length:", len(text))

    print("\nPreview:\n")

    print(text[:5000])


if __name__ == "__main__":
    main()