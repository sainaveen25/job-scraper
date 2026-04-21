from __future__ import annotations

from job_scraper.models import BroadQuery


def build_global_queries(categories: list[str], locations: list[str]) -> list[dict[str, str]]:
    queries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for category in categories:
        for location in locations:
            key = (category.casefold(), location.casefold())
            if key in seen:
                continue
            seen.add(key)
            queries.append(BroadQuery(category=category, location=location, query=f"{category} jobs {location}").__dict__)
    return queries

