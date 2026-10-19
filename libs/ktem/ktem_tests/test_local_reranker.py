"""Tests for the local lexical reranker and the "configured but unusable" fallback.

The shipped default reranker is Cohere; without a key it returned the list unchanged
while the UI said reranking was on. The fallback (``resolve_reranker``) picks a
reranker that can actually run, and this module pins both halves: the scoring itself
and the choice.
"""

from __future__ import annotations

import pytest

from kotaemon.base import RetrievedDocument
from kotaemon.rerankings import CohereReranking, LocalLexicalReranker, resolve_reranker
from kotaemon.rerankings.local_lexical import lexical_score, tokenize


def doc(text, score=0.5, page="1"):
    return RetrievedDocument(text=text, metadata={"page_label": page}, score=score)


# --------------------------------------------------------------------------- #
# tokenising and scoring
# --------------------------------------------------------------------------- #
def test_chinese_is_tokenised_into_character_bigrams():
    # no segmenter is available offline: bigrams are the standard cheap substitute
    assert tokenize("加分细则") == ["加分", "分细", "细则"]


def test_latin_words_and_digits_are_kept_as_terms():
    assert "python" in tokenize("Python 3.12 的新特性")
    assert "3" not in tokenize("Python 3.12")  # single characters are noise


def test_a_single_cjk_character_stays_a_term():
    assert tokenize("分") == ["分"]


def test_partial_overlap_scores_between_zero_and_one():
    """Coverage of the question's terms, not their frequency.

    "加分细则是什么" has six bigrams (加分/分细/细则/则是/是什/什么); the document
    covers the first three, so the score is 3/6.
    """
    terms = tokenize("加分细则是什么")
    score = lexical_score(terms, "加分细则说明了加分办法")

    assert score == pytest.approx(0.5)


def test_a_fully_covered_question_scores_one():
    terms = tokenize("满分多少分")
    assert lexical_score(terms, "满分多少分") == pytest.approx(1.0)


def test_unrelated_text_scores_zero():
    assert lexical_score(tokenize("宿舍几点熄灯"), "国家励志奖学金评审办法") == 0.0


def test_an_empty_query_scores_zero():
    assert lexical_score([], "任何内容") == 0.0


# --------------------------------------------------------------------------- #
# the file name counts as overlap (§5.23)
# --------------------------------------------------------------------------- #
def named_doc(text, name, score=0.5):
    return RetrievedDocument(text=text, metadata={"file_name": name}, score=score)


def test_the_file_name_counts_as_overlap():
    """A question that names the file shares no words with code, but it shares the name.

    Without the name every chunk of a code file scores 0, the panel then falls back to
    vector similarity, and relevant code chunks look the same as unrelated notices
    (MODIFICATIONS §5.23).
    """
    reranker = LocalLexicalReranker()
    code = named_doc(
        "def gaussian(X, num_centers=10):\n    return np.exp(-d)", "代码.txt"
    )
    prose = named_doc("某学院入党积极分子积分细则", "积分细则.pdf")

    result = reranker.run([prose, code], "代码.txt讲了什么算法")

    assert result[0] is code
    assert code.metadata["rerank_score"] > prose.metadata["rerank_score"]


def test_the_file_name_alone_does_not_rescue_an_unrelated_file():
    reranker = LocalLexicalReranker()
    code = named_doc("def gaussian(X): ...", "main.py")

    reranker.run([code], "代码.txt讲了什么算法")

    assert code.metadata["rerank_score"] == 0.0


# --------------------------------------------------------------------------- #
# the reranker itself
# --------------------------------------------------------------------------- #
def test_documents_are_reordered_by_overlap():
    reranker = LocalLexicalReranker()
    unrelated = doc("宿舍熄灯时间说明", score=0.9)
    matching = doc("加分细则：学科竞赛加分标准", score=0.4)

    result = reranker.run([unrelated, matching], "加分细则是什么")

    assert result[0] is matching
    assert matching.metadata["rerank_score"] > unrelated.metadata["rerank_score"]


def test_the_retrieval_score_is_preserved():
    """The refusal gate is calibrated on retrieval similarity (§5.8)."""
    reranker = LocalLexicalReranker()
    matching = doc("加分细则", score=0.42)

    reranker.run([matching], "加分细则")

    assert matching.score == 0.42
    assert matching.metadata["rerank_score"] > 0


def test_reranking_reorders_by_default_and_never_drops():
    reranker = LocalLexicalReranker()
    docs = [doc("无关内容", score=0.9), doc("加分细则", score=0.1)]

    result = reranker.run(docs, "加分细则")

    assert len(result) == 2  # a reranker that drops documents turns a miss permanent


def test_min_coverage_filters_when_asked():
    reranker = LocalLexicalReranker(min_coverage=0.5)
    docs = [doc("加分细则", score=0.1), doc("宿舍熄灯", score=0.9)]

    result = reranker.run(docs, "加分细则")

    assert [d.text for d in result] == ["加分细则"]


def test_top_k_truncates_when_asked():
    reranker = LocalLexicalReranker(top_k=1)
    docs = [doc("加分细则", score=0.1), doc("加分细则补充", score=0.2)]

    assert len(reranker.run(docs, "加分细则")) == 1


def test_equal_overlap_keeps_the_retrieval_order():
    reranker = LocalLexicalReranker()
    first = doc("加分细则 A", score=0.8)
    second = doc("加分细则 B", score=0.7)

    result = reranker.run([first, second], "加分细则")

    assert [d is first for d in result][0] is True


# --------------------------------------------------------------------------- #
# picking the reranker
# --------------------------------------------------------------------------- #
def test_an_available_reranker_is_used():
    custom = LocalLexicalReranker(top_k=3)
    resolved = resolve_reranker("local", {"local": custom}.get)

    assert resolved is custom


def test_an_unavailable_reranker_falls_back_to_the_local_one():
    """Cohere without a key is a configured no-op; the local lexer is not."""
    cohere = CohereReranking(cohere_api_key="", model_name="rerank-v4.0-fast")

    resolved = resolve_reranker("cohere", {"cohere": cohere}.get)

    assert isinstance(resolved, LocalLexicalReranker)
    assert not cohere.is_available()


def test_an_unknown_name_falls_back_to_the_local_one():
    assert isinstance(resolve_reranker("gone", {}.get), LocalLexicalReranker)


def test_an_empty_configuration_falls_back_to_the_local_one():
    assert isinstance(resolve_reranker(None, {}.get), LocalLexicalReranker)


def test_cohere_reports_availability_by_its_key():
    assert CohereReranking(cohere_api_key="real-key", model_name="x").is_available()
    assert not CohereReranking(
        cohere_api_key="COHERE_API_KEY", model_name="x"
    ).is_available()


def test_the_local_reranker_is_always_available():
    assert LocalLexicalReranker().is_available()
