"""Tests for batching inside the OpenAI-compatible embeddings."""

from __future__ import annotations

import pytest

from kotaemon.embeddings.openai import BaseOpenAIEmbeddings, OpenAIEmbeddings

#: batch sizes the fake provider was asked for, in order
CALLS: list[int] = []


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def dict(self):
        return self._payload


class _FakeEmbeddings(OpenAIEmbeddings):
    """Records the batch sizes it was asked for and enforces a provider limit."""

    LIMIT = 10
    ERROR_TEXT: str | None = None
    REVERSED = False

    def openai_response(self, client, **kwargs):
        batch = kwargs["input"]
        CALLS.append(len(batch))
        if len(batch) > self.LIMIT:
            raise ValueError(
                self.ERROR_TEXT
                or (
                    "<400> InternalError.Algo.InvalidParameter: Value error, batch "
                    f"size is invalid, it should not be larger than {self.LIMIT}."
                )
            )
        items = [
            {"index": index, "embedding": [float(len(text))]}
            for index, text in enumerate(batch)
        ]
        if self.REVERSED:
            items.reverse()
        return _Response({"data": items})


def make(limit=10, error_text=None, reversed_items=False):
    class _Fake(_FakeEmbeddings):
        LIMIT = limit
        ERROR_TEXT = error_text
        REVERSED = reversed_items

    return _Fake(model="fake", api_key="test")


@pytest.fixture(autouse=True)
def _reset_calls():
    CALLS.clear()
    yield
    CALLS.clear()


def test_embeddings_are_split_into_batches():
    embeddings = make()
    embeddings.batch_size = 3

    result = embeddings._embed_all(None, ["a", "bbb", "ccccc", "d"])

    assert CALLS == [3, 1]
    # the embedding of each input must stay next to it
    assert [item["embedding"] for item in result] == [[1.0], [3.0], [5.0], [1.0]]


def test_a_rejected_batch_is_retried_with_the_limit_the_provider_names():
    """A too-large batch is a configuration guess, not a document defect.

    DashScope rejects more than 10 inputs ("batch size is invalid, it should not be
    larger than 10"), while the shipped configuration asked for 25. Every document
    with more than ten chunks therefore failed to index — the upload reported an
    error and the file never answered a question.
    """
    embeddings = make(limit=10)
    embeddings.batch_size = 25

    texts = [f"text-{i}" for i in range(25)]
    result = embeddings._embed_all(None, texts)

    assert len(result) == 25
    assert CALLS[0] == 25  # the too-large attempt
    assert CALLS[1] == 10  # …then the limit taken from the message
    assert embeddings.batch_size == 10  # kept for the rest of the run
    assert result[3]["embedding"] == [float(len("text-3"))]


def test_the_batch_is_halved_when_the_error_names_no_limit():
    embeddings = make(limit=8, error_text="request rejected: too many inputs in one call")
    embeddings.batch_size = 32

    result = embeddings._embed_all(None, [f"t{i}" for i in range(32)])

    assert CALLS[:3] == [32, 16, 8]
    assert all(size <= 8 for size in CALLS[3:])
    assert len(result) == 32


def test_unrelated_errors_are_not_retried():
    class _Broken(_FakeEmbeddings):
        def openai_response(self, client, **kwargs):
            raise ValueError("401 invalid api key")

    embeddings = _Broken(model="fake", api_key="test")

    with pytest.raises(ValueError, match="invalid api key"):
        embeddings._embed_all(None, ["a", "b"])


def test_a_batch_of_one_that_still_fails_raises_instead_of_looping():
    embeddings = make(limit=0)
    embeddings.batch_size = 4

    with pytest.raises(ValueError, match="batch"):
        embeddings._embed_all(None, ["only"])


def test_empty_input_makes_no_request():
    embeddings = make()

    assert embeddings._embed_all(None, []) == []
    assert CALLS == []


def test_response_order_is_restored_within_a_batch():
    embeddings = make(reversed_items=True)
    embeddings.batch_size = 4

    result = embeddings._embed_all(None, ["a", "bb", "ccc"])

    assert [item["embedding"] for item in result] == [[1.0], [2.0], [3.0]]


def test_provider_error_text_is_parsed_without_the_generic_hint():
    error = ValueError("InvalidParameter: the batch should have at most 4 items")
    assert BaseOpenAIEmbeddings._smaller_batch_size(20, error) == 4


def test_non_batch_error_keeps_the_batch_size():
    error = ConnectionError("connection reset by peer")
    assert BaseOpenAIEmbeddings._smaller_batch_size(20, error) is None
    assert BaseOpenAIEmbeddings._smaller_batch_size(1, ValueError("batch size")) is None
