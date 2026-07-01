from app.search.providers.duckduckgo_provider import DuckDuckGoProvider


def main():

    provider = DuckDuckGoProvider()

    results = provider.search(
        query="Healthcare companies Bangalore",
        max_results=5
    )

    print("\nSearch Results\n")

    for result in results:
        print("=" * 60)
        print("Title :", result.title)
        print("URL   :", result.url)
        print("Rank  :", result.rank)
        print("Source:", result.source)
        print("Snippet:")
        print(result.snippet)
        print()


if __name__ == "__main__":
    main()