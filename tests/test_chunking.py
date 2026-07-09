from src.chunking import split_sentences


def test_splits_plain_sentences():
    text = "First sentence. Second sentence. Third one?"
    assert split_sentences(text) == [
        "First sentence.",
        "Second sentence.",
        "Third one?",
    ]


def test_keeps_citation_abbreviations_together():
    text = (
        'Clifford Cobb, Ted Halstead and Jonathan Rowe. "If the GDP is up, '
        'why is America down?" The Atlantic Monthly, vol. 276, no. 4, '
        "October 1995, pages 59–78"
    )
    result = split_sentences(text)
    assert len(result) == 1
    assert "vol. 276, no. 4" in result[0]


def test_empty_and_whitespace_input():
    assert split_sentences("") == []
    assert split_sentences("   ") == []
    assert split_sentences(None) == []
