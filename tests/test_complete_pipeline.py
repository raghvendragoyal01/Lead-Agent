import json

from app.pipeline.pipeline import LeadDiscoveryPipeline


def main():

    pipeline = LeadDiscoveryPipeline()

    homepage = "https://www.mozilla.org/"

    lead = pipeline.run(homepage)

    print("\n==============================")
    print("FINAL LEAD")
    print("==============================\n")

    print(lead.model_dump_json(indent=4))

    with open("result.json", "w", encoding="utf-8") as f:

        json.dump(
            lead.model_dump(mode="json"),
            f,
            indent=4,
            ensure_ascii=False,
        )

    print("\n✅ Result saved to result.json")


if __name__ == "__main__":
    main()