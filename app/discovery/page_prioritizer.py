from typing import List

from app.schemas.page_schema import DiscoveredPage


class PagePrioritizer:
    """
    Assigns priority scores to discovered pages.
    """

    PRIORITIES = {
        "contact": 10,
        "about": 9,
        "leadership": 9,
        "management": 9,
        "team": 8,
        "company": 8,
        "office": 7,
        "location": 7,
        "corporate": 7,
        "investor": 5,
        "careers": 2,
        "career": 2,
        "blog": 0,
        "news": 0,
        "privacy": -1,
        "terms": -1,
        "cookie": -1,
    }

    def prioritize(
        self,
        pages: List[DiscoveredPage],
    ) -> List[DiscoveredPage]:

        prioritized = []

        for page in pages:

            text = f"{page.text} {page.url}".lower()

            score = 1

            for keyword, value in self.PRIORITIES.items():

                if keyword in text:
                    score = value
                    break

            prioritized.append(
                page.model_copy(
                    update={"score": score}
                )
            )

        prioritized.sort(
            key=lambda x: x.score,
            reverse=True,
        )

        return prioritized