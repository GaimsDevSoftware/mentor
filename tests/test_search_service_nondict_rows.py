import asyncio

import services.search.service as svc_mod
from services.search.service import SearchService


def test_search_skips_non_dict_results(monkeypatch):
    # comprehensive_web_search aggregates external provider + cache results;
    # a malformed row (string/None) made the old loop call r.get and crash,
    # losing the whole search. SearchService.search runs it via asyncio.to_thread
    # with return_sources=True, so the mock is sync and returns (context, rows).
    def fake_search(query, max_pages=10, return_sources=True, **kwargs):
        rows = [
            {"url": "https://a.com", "title": "A", "snippet": "x"},
            "junk-row",
            None,
            {"url": "https://b.com", "title": "B", "snippet": "y"},
        ]
        return ("context", rows)

    monkeypatch.setattr(svc_mod, "comprehensive_web_search", fake_search)
    svc = SearchService()
    res = asyncio.run(svc.search("anything"))
    assert [r.url for r in res.results] == ["https://a.com", "https://b.com"]
    assert res.total == 2
