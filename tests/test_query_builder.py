from app.search.query_builder import QueryBuilder


def main():
    builder = QueryBuilder(max_queries=10)

    queries = builder.build_queries(
        industry="Healthcare",
        location="Bangalore",
        designation="CTO",
        company_size="50-500",
        keywords=["AI", "SaaS"]
    )

    print("\nGenerated Search Queries:\n")

    for i, query in enumerate(queries, start=1):
        print(f"{i}. {query}")


if __name__ == "__main__":
    main()