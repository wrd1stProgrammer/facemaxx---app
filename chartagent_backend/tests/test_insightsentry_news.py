from __future__ import annotations

from app.insightsentry import _NewsRow, _select_recent_news


def test_news_selection_keeps_ten_items_from_each_24_hour_bucket() -> None:
    now = 2_000_000_000
    rows = [
        _NewsRow(title=f"recent-{index}", published_at=now - index * 1_800)
        for index in range(12)
    ] + [
        _NewsRow(title=f"prior-{index}", published_at=now - 86_400 - index * 1_800)
        for index in range(12)
    ] + [
        _NewsRow(title="expired", published_at=now - 172_801),
        _NewsRow(title="recent-0", published_at=now - 300),
        _NewsRow(title="recent-0", published_at=now - 600),
    ]

    selected = _select_recent_news(rows, now_timestamp=now)

    assert len(selected) == 20
    assert [item.title for item in selected[:10]] == [f"recent-{index}" for index in range(10)]
    assert [item.title for item in selected[10:]] == [f"prior-{index}" for index in range(10)]
    assert len({item.title for item in selected}) == 20


def test_news_selection_accepts_millisecond_timestamps() -> None:
    now = 2_000_000_000
    selected = _select_recent_news(
        [_NewsRow(title="milliseconds", published_at=(now - 3_600) * 1_000)],
        now_timestamp=now,
    )

    assert [item.title for item in selected] == ["milliseconds"]
