from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    retrieved_at: str
    provider: str
