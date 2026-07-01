from app.search.search_client import SearchClient


def main():

    client = SearchClient(max_queries=3)

    results = client.search(
        industry="Healthcare",
        location="Bangalore",
        designation="CEO"
    )

    print("\nFinal Results\n")

    for result in results:

        print("=" * 70)

        print(result.title)

        print(result.url)

        print(result.source)

        print(result.rank)

        print()


if __name__ == "__main__":
    main()