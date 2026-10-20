import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Generator

from decouple import config
from ktem.embeddings.manager import embedding_models_manager as embeddings
from ktem.llms.manager import llms
from ktem.reasoning.prompt_optimization import (
    DecomposeQuestionPipeline,
    RewriteQuestionPipeline,
)
from ktem.utils.i18n import tr
from ktem.utils.render import (
    Render,
    has_rerank_score,
    relevance_score_of,
    reranking_score_of,
)
from ktem.utils.trace import TraceRecorder
from ktem.utils.visualize_cited import CreateCitationVizPipeline
from plotly.io import to_json
from theflow.settings import settings as flowsettings

from kotaemon.abstain import best_similarity, should_refuse
from kotaemon.base import (
    AIMessage,
    BaseComponent,
    Document,
    HumanMessage,
    Node,
    RetrievedDocument,
    SystemMessage,
)
from kotaemon.indices.qa.citation_qa import (
    CONTEXT_RELEVANT_WARNING_SCORE,
    DEFAULT_QA_TEXT_PROMPT,
    AnswerWithContextPipeline,
)
from kotaemon.indices.qa.citation_qa_inline import AnswerWithInlineCitation
from kotaemon.indices.qa.format_context import PrepareEvidencePipeline
from kotaemon.indices.qa.utils import replace_think_tag_with_details
from kotaemon.llms import ChatLLM
from kotaemon.llms.usage import usage

from ..utils import SUPPORTED_LANGUAGE_MAP
from .base import BaseReasoning

logger = logging.getLogger(__name__)

#: Refusal gate (ROADMAP B4). Messages keep the i18n discipline of the project: the
#: source string is English and ``tr()`` looks it up in the catalog, so the catalog
#: stays the only place with translated text.
ABSTAIN_INFO_TEMPLATE = (
    "<h5>No strong evidence for this question: the best match scores {score:.2f}, "
    "below the {threshold:.2f} threshold, so the answer was skipped.</h5>"
)
ABSTAIN_ANSWER_TEMPLATE = (
    "The knowledge base has no evidence for this question "
    "(best match {score:.2f}, below the {threshold:.2f} threshold).\n\n"
    "What to try:\n"
    "1. use more specific keywords;\n"
    "2. check that the file finished indexing (Files tab shows blocks and loader);\n"
    '3. under "Search in File(s)", pick the file explicitly.'
)


def abstain_threshold() -> float:
    """Similarity below which an answer is refused; ``0`` disables the gate."""
    return float(getattr(flowsettings, "KH_ABSTAIN_SCORE_THRESHOLD", 0.0) or 0.0)


def abstain_term_floor() -> float:
    """Similarity that still counts once a rare entity term matched the question."""
    return float(getattr(flowsettings, "KH_ABSTAIN_TERM_FLOOR", 0.33) or 0.0)


def abstain_log_path() -> Path:
    configured = getattr(flowsettings, "KH_ABSTAIN_LOG", None)
    if configured:
        return Path(configured)
    data_dir = Path(getattr(flowsettings, "KH_APP_DATA_DIR", "."))
    return data_dir / "abstained_queries.jsonl"


def log_abstention(
    question: str, score: float, threshold: float, reason: str = "low_score"
) -> None:
    """Record a refused query so the gate can be audited (ROADMAP B4)."""
    path = abstain_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "time": datetime.now().isoformat(timespec="seconds"),
                        "question": question,
                        "best_score": round(score, 4),
                        "threshold": threshold,
                        "reason": reason,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError as exc:  # a log failure must never break the answer path
        logger.warning("could not write the abstention log %s: %s", path, exc)


def abstain_events(
    question: str, docs: list, threshold: float | None = None
) -> list[Document]:
    """Documents to emit when the evidence is too weak (empty when it is not).

    Kept as a module function (rather than a pipeline method) so the decision and the
    text can be tested without building the whole reasoning pipeline.

    The documents and the question are passed through so a rare entity term (a name in
    a spreadsheet row, an id) can lower the bar: a dense table answers a correct
    question at a similarity far below what prose reaches (MODIFICATIONS §5.8).
    """
    threshold = abstain_threshold() if threshold is None else threshold
    scores = [float(getattr(doc, "score", 0.0) or 0.0) for doc in docs]
    if not should_refuse(
        scores,
        threshold,
        documents=docs,
        question=question,
        term_floor=abstain_term_floor(),
    ):
        return []

    best = best_similarity(scores) or 0.0
    log_abstention(question, best, threshold)
    return [
        Document(
            channel="info",
            content=tr(ABSTAIN_INFO_TEMPLATE).format(score=best, threshold=threshold),
        ),
        Document(
            channel="chat",
            content=tr(ABSTAIN_ANSWER_TEMPLATE).format(
                score=best, threshold=threshold
            ),
        ),
    ]


class AddQueryContextPipeline(BaseComponent):

    n_last_interactions: int = 5
    llm: ChatLLM = Node(default_callback=lambda _: llms.get_default())

    def run(self, question: str, history: list) -> Document:
        messages = [
            SystemMessage(
                content="Below is a history of the conversation so far, and a new "
                "question asked by the user that needs to be answered by searching "
                "in a knowledge base.\nYou have access to a Search index "
                "with 100's of documents.\nGenerate a search query based on the "
                "conversation and the new question.\nDo not include cited source "
                "filenames and document names e.g info.txt or doc.pdf in the search "
                "query terms.\nDo not include any text inside [] or <<>> in the "
                "search query terms.\nDo not include any special characters like "
                "'+'.\nIf the question is not in English, rewrite the query in "
                "the language used in the question.\n If the question contains enough "
                "information, return just the number 1\n If it's unnecessary to do "
                "the searching, return just the number 0."
            ),
            HumanMessage(content="How did crypto do last year?"),
            AIMessage(
                content="Summarize Cryptocurrency Market Dynamics from last year"
            ),
            HumanMessage(content="What are my health plans?"),
            AIMessage(content="Show available health plans"),
        ]
        for human, ai in history[-self.n_last_interactions :]:
            messages.append(HumanMessage(content=human))
            messages.append(AIMessage(content=ai))

        messages.append(HumanMessage(content=f"Generate search query for: {question}"))

        resp = self.llm(messages).text
        if resp == "0":
            return Document(content="")

        if resp == "1":
            return Document(content=question)

        return Document(content=resp)


class FullQAPipeline(BaseReasoning):
    """Question answering pipeline. Handle from question to answer"""

    class Config:
        allow_extra = True

    # configuration parameters
    trigger_context: int = 150
    use_rewrite: bool = False

    retrievers: list[BaseComponent]

    evidence_pipeline: PrepareEvidencePipeline = PrepareEvidencePipeline.withx()
    answering_pipeline: AnswerWithContextPipeline
    rewrite_pipeline: RewriteQuestionPipeline | None = None
    create_citation_viz_pipeline: CreateCitationVizPipeline = Node(
        default_callback=lambda _: CreateCitationVizPipeline(
            embedding=embeddings.get_default()
        )
    )
    add_query_context: AddQueryContextPipeline = AddQueryContextPipeline.withx()

    def retrieve(
        self, message: str, history: list
    ) -> tuple[list[RetrievedDocument], list[Document]]:
        """Retrieve the documents based on the message"""
        # if len(message) < self.trigger_context:
        #     # prefer adding context for short user questions, avoid adding context for
        #     # long questions, as they are likely to contain enough information
        #     # plus, avoid the situation where the original message is already too long
        #     # for the model to handle
        #     query = self.add_query_context(message, history).content
        # else:
        #     query = message
        # print(f"Rewritten query: {query}")
        query = None
        if not query:
            # TODO: previously return [], [] because we think this message as something
            # like "Hello", "I need help"...
            query = message

        docs, doc_ids = [], []
        plot_docs = []

        for idx, retriever in enumerate(self.retrievers):
            retriever_node = self._prepare_child(retriever, f"retriever_{idx}")
            retriever_docs = retriever_node(text=query)

            retriever_docs_text = []
            retriever_docs_plot = []

            for doc in retriever_docs:
                if doc.metadata.get("type", "") == "plot":
                    retriever_docs_plot.append(doc)
                else:
                    retriever_docs_text.append(doc)

            for doc in retriever_docs_text:
                if doc.doc_id not in doc_ids:
                    docs.append(doc)
                    doc_ids.append(doc.doc_id)

            plot_docs.extend(retriever_docs_plot)

        info = [
            Document(
                channel="info",
                content=Render.collapsible_with_header(doc, open_collapsible=True),
            )
            for doc in docs
        ] + [
            Document(
                channel="plot",
                content=doc.metadata.get("data", ""),
            )
            for doc in plot_docs
        ]

        return docs, info

    def prepare_mindmap(self, answer) -> Document | None:
        mindmap = answer.metadata["mindmap"]
        if mindmap:
            mindmap_text = mindmap.text
            mindmap_svg = dedent(
                """
                <div class="markmap">
                <script type="text/template">
                ---
                markmap:
                    colorFreezeLevel: 2
                    activeNode:
                        placement: center
                    initialExpandLevel: 4
                    maxWidth: 200
                ---
                {}
                </script>
                </div>
                """
            ).format(mindmap_text)

            mindmap_content = Document(
                channel="info",
                content=Render.collapsible(
                    header="""
                    <i>Mindmap</i>
                    <a href="#" id='mindmap-toggle'>
                        [Expand]</a>
                    <a href="#" id='mindmap-export'>
                        [Export]</a>""",
                    content=mindmap_svg,
                    open=True,
                ),
            )
        else:
            mindmap_content = None

        return mindmap_content

    def prepare_citation_viz(self, answer, question, docs) -> Document | None:
        doc_texts = [doc.text for doc in docs]
        citation_plot = None
        plot_content = None

        if answer.metadata["citation_viz"] and len(docs) > 1:
            try:
                citation_plot = self.create_citation_viz_pipeline(doc_texts, question)
            except Exception as e:
                print("Failed to create citation plot:", e)

            if citation_plot:
                plot = to_json(citation_plot)
                plot_content = Document(channel="plot", content=plot)

        return plot_content

    def structured_evidence(self, answer, docs) -> list[dict]:
        """The evidence as JSON-friendly records for the web UI (MODIFICATIONS §5.25).

        The classic panel renders HTML; the web UI needs data. Both are produced
        from the same ``docs`` and the same score helpers, so they cannot disagree.
        """
        try:
            spans = self.answering_pipeline.match_evidence_with_context(answer, docs)
        except Exception as exc:  # noqa: BLE001 - evidence rendering is best effort
            logger.warning("could not match evidence spans: %s", exc)
            spans = {}

        items: list[dict] = []
        for doc in docs:
            metadata = getattr(doc, "metadata", None) or {}
            raw_spans = spans.get(doc.doc_id, []) if isinstance(spans, dict) else []
            clean_spans = [
                {
                    "start": int(span.get("start", 0)),
                    "end": int(span.get("end", 0)),
                    "idx": span.get("idx"),
                }
                for span in raw_spans
                if isinstance(span, dict)
            ]
            try:
                score = float(relevance_score_of(doc))
            except Exception:  # noqa: BLE001
                score = 0.0
            try:
                llm_score = round(float(metadata.get("llm_trulens_score") or 0.0), 2)
            except (TypeError, ValueError):
                llm_score = 0.0
            # ``None`` means no reranker scored this chunk (the entity-row pass adds
            # chunks after reranking). The panel must not show that as ``0.0`` — a
            # zero is the reranker's verdict, a missing score is not (MODIFICATIONS
            # §5.32). ``score`` keeps its meaning for sorting.
            rerank_score = reranking_score_of(doc) if has_rerank_score(doc) else None
            items.append(
                {
                    "id": doc.doc_id,
                    "file_id": metadata.get("file_id"),
                    "file_name": metadata.get("file_name", "<evidence>"),
                    "page": metadata.get("page_label"),
                    "type": metadata.get("type", "text"),
                    "score": score,
                    "vector_score": round(float(getattr(doc, "score", 0.0) or 0.0), 4),
                    "rerank_score": rerank_score,
                    "llm_score": llm_score,
                    "text": (doc.text or "")[:4000],
                    "file_path": metadata.get("file_path", ""),
                    "cited": bool(clean_spans),
                    "entity_row": bool(metadata.get("entity_row", False)),
                    "spans": clean_spans,
                }
            )

        # cited chunks first, then by the score the panel shows (MODIFICATIONS §5.23)
        items.sort(key=lambda item: (not item["cited"], -item["score"]))
        return items

    def show_citations_and_addons(self, answer, docs, question):
        # show the evidence
        with_citation, without_citation = self.answering_pipeline.prepare_citations(
            answer, docs
        )
        mindmap_output = self.prepare_mindmap(answer)
        citation_plot_output = self.prepare_citation_viz(answer, question, docs)

        # Structured channels for the web UI (MODIFICATIONS §5.25). The classic
        # page ignores unknown channels, so both UIs read the same run.
        yield Document(channel="evidence", content=self.structured_evidence(answer, docs))
        mindmap_source = (getattr(answer, "metadata", None) or {}).get("mindmap")
        if mindmap_source is not None and getattr(mindmap_source, "text", ""):
            yield Document(channel="mindmap", content=mindmap_source.text)

        if not with_citation and not without_citation:
            yield Document(
                channel="info",
                content=Render.empty_state(
                    tr("No evidence yet"),
                    tr("Evidence will appear here after you ask a question."),
                ),
            )
        else:
            # clear the Info panel
            max_llm_rerank_score = max(
                doc.metadata.get("llm_trulens_score", 0.0) for doc in docs
            )
            has_llm_score = any("llm_trulens_score" in doc.metadata for doc in docs)
            # clear previous info
            yield Document(channel="info", content=None)

            # yield mindmap output
            if mindmap_output:
                yield mindmap_output

            # yield citation plot output
            if citation_plot_output:
                yield citation_plot_output

            # yield warning message
            if has_llm_score and max_llm_rerank_score < CONTEXT_RELEVANT_WARNING_SCORE:
                yield Document(
                    channel="info",
                    content=(
                        "<h5>WARNING! Context relevance score is low. "
                        "Double check the model answer for correctness.</h5>"
                    ),
                )

            # show QA score
            qa_score = (
                round(answer.metadata["qa_score"], 2)
                if answer.metadata.get("qa_score")
                else None
            )
            if qa_score:
                yield Document(
                    channel="info",
                    content=f"<h5>Answer confidence: {qa_score}</h5>",
                )

            yield from with_citation
            if without_citation:
                yield from without_citation

    async def ainvoke(  # type: ignore
        self, message: str, conv_id: str, history: list, **kwargs  # type: ignore
    ) -> Document:  # type: ignore
        raise NotImplementedError

    def stream(  # type: ignore
        self, message: str, conv_id: str, history: list, **kwargs  # type: ignore
    ) -> Generator[Document, None, Document]:
        if self.use_rewrite and self.rewrite_pipeline:
            print("Chosen rewrite pipeline", self.rewrite_pipeline)
            message = self.rewrite_pipeline(question=message).text
            print("Rewrite result", message)

        started = time.perf_counter()
        usage_before = usage.snapshot()
        trace = TraceRecorder()

        print(f"Retrievers {self.retrievers}")
        # should populate the context
        docs, infos = self.retrieve(message, history)
        print(f"Got {len(docs)} retrieved documents")
        yield from infos

        # refusal gate: no evidence strong enough means no answer from memory
        refused = abstain_events(message, docs)
        if refused:
            print("Refusing to answer: the evidence is too weak")
            # still show what was retrieved: the web UI needs the chunks and their
            # scores to explain the refusal (MODIFICATIONS §5.25)
            yield Document(channel="evidence", content=self.structured_evidence(None, docs))
            yield from refused
            self._trace_query(
                trace,
                message,
                docs,
                abstained=True,
                started=started,
                usage_before=usage_before,
                answer_text=refused[-1].content,
            )
            return Document(text=refused[-1].content, channel="chat")

        evidence_mode, evidence, images = self.evidence_pipeline(docs).content

        def generate_relevant_scores():
            nonlocal docs
            docs = self.retrievers[0].generate_relevant_scores(message, docs)

        # generate relevant score using
        if evidence and self.retrievers:
            scoring_thread = threading.Thread(target=generate_relevant_scores)
            scoring_thread.start()
        else:
            scoring_thread = None

        answer = yield from self.answering_pipeline.stream(
            question=message,
            history=history,
            evidence=evidence,
            evidence_mode=evidence_mode,
            images=images,
            conv_id=conv_id,
            **kwargs,
        )

        # check <think> tag from reasoning models
        processed_answer = replace_think_tag_with_details(answer.text)
        if processed_answer != answer.text:
            # clear the chat message and render again
            yield Document(channel="chat", content=None)
            yield Document(channel="chat", content=processed_answer)

        # show the evidence
        if scoring_thread:
            scoring_thread.join()

        self._trace_query(
            trace,
            message,
            docs,
            abstained=False,
            started=started,
            usage_before=usage_before,
            answer_text=answer.text,
        )

        yield from self.show_citations_and_addons(answer, docs, message)

        return answer

    def _trace_query(
        self,
        trace: TraceRecorder,
        question: str,
        docs: list,
        *,
        abstained: bool,
        started: float,
        usage_before: dict,
        answer_text: str = "",
    ) -> None:
        """Write one trace line for this question (no-op when tracing is off)."""
        if not trace.enabled:
            return
        scores = [float(getattr(doc, "score", 0.0) or 0.0) for doc in docs]
        reranked = (
            bool(getattr(self.retrievers[0], "rerankers", []))
            if self.retrievers
            else False
        )
        trace.record(
            question=question,
            retrieved=len(docs),
            top_score=round(best_similarity(scores) or 0.0, 4),
            reranked=reranked,
            abstained=abstained,
            answer_chars=len(answer_text or ""),
            total_ms=round((time.perf_counter() - started) * 1000, 1),
            **usage.since(usage_before),
        )

    @classmethod
    def prepare_pipeline_instance(cls, settings, retrievers):
        return cls(
            retrievers=retrievers,
            rewrite_pipeline=None,
        )

    @classmethod
    def get_pipeline(cls, settings, states, retrievers):
        """Get the reasoning pipeline

        Args:
            settings: the settings for the pipeline
            retrievers: the retrievers to use
        """
        max_context_length_setting = settings.get("reasoning.max_context_length", 32000)

        pipeline = cls.prepare_pipeline_instance(settings, retrievers)

        prefix = f"reasoning.options.{cls.get_info()['id']}"
        llm_name = settings.get(f"{prefix}.llm", None)
        llm = llms.get(llm_name, llms.get_default())

        # prepare evidence pipeline configuration
        evidence_pipeline = pipeline.evidence_pipeline
        evidence_pipeline.max_context_length = max_context_length_setting

        # answering pipeline configuration
        use_inline_citation = settings[f"{prefix}.highlight_citation"] == "inline"

        if use_inline_citation:
            answer_pipeline = pipeline.answering_pipeline = AnswerWithInlineCitation()
        else:
            answer_pipeline = pipeline.answering_pipeline = AnswerWithContextPipeline()

        answer_pipeline.llm = llm
        answer_pipeline.citation_pipeline.llm = llm
        answer_pipeline.n_last_interactions = settings[f"{prefix}.n_last_interactions"]
        answer_pipeline.enable_citation = (
            settings[f"{prefix}.highlight_citation"] != "off"
        )
        answer_pipeline.enable_mindmap = settings[f"{prefix}.create_mindmap"]
        answer_pipeline.enable_citation_viz = settings[f"{prefix}.create_citation_viz"]
        answer_pipeline.use_multimodal = settings[f"{prefix}.use_multimodal"]
        answer_pipeline.system_prompt = settings[f"{prefix}.system_prompt"]
        answer_pipeline.qa_template = settings[f"{prefix}.qa_prompt"]
        answer_pipeline.lang = SUPPORTED_LANGUAGE_MAP.get(
            settings["reasoning.lang"], "English"
        )

        pipeline.add_query_context.llm = llm
        pipeline.add_query_context.n_last_interactions = settings[
            f"{prefix}.n_last_interactions"
        ]

        pipeline.trigger_context = settings[f"{prefix}.trigger_context"]
        pipeline.use_rewrite = states.get("app", {}).get("regen", False)
        if pipeline.rewrite_pipeline:
            pipeline.rewrite_pipeline.llm = llm
            pipeline.rewrite_pipeline.lang = SUPPORTED_LANGUAGE_MAP.get(
                settings["reasoning.lang"], "English"
            )
        return pipeline

    @classmethod
    def get_user_settings(cls) -> dict:
        from ktem.llms.manager import llms

        llm = ""
        choices = [("(default)", "")]
        try:
            choices += [(_, _) for _ in llms.options().keys()]
        except Exception as e:
            logger.exception(f"Failed to get LLM options: {e}")

        return {
            "llm": {
                "name": "Language model",
                "value": llm,
                "component": "dropdown",
                "choices": choices,
                "special_type": "llm",
                "info": (
                    "The language model to use for generating the answer. If None, "
                    "the application default language model will be used."
                ),
            },
            "highlight_citation": {
                "name": "Citation style",
                "value": (
                    "highlight"
                    if not config("USE_LOW_LLM_REQUESTS", default=False, cast=bool)
                    else "off"
                ),
                "component": "radio",
                "choices": [
                    ("citation: highlight", "highlight"),
                    ("citation: inline", "inline"),
                    ("no citation", "off"),
                ],
            },
            "create_mindmap": {
                "name": "Create Mindmap",
                "value": False,
                "component": "checkbox",
            },
            "create_citation_viz": {
                "name": "Create Embeddings Visualization",
                "value": False,
                "component": "checkbox",
            },
            "use_multimodal": {
                "name": "Use Multimodal Input",
                "value": False,
                "component": "checkbox",
            },
            "system_prompt": {
                "name": "System Prompt",
                "value": ("This is a question answering system."),
            },
            "qa_prompt": {
                "name": "QA Prompt (contains {context}, {question}, {lang})",
                "value": DEFAULT_QA_TEXT_PROMPT,
            },
            "n_last_interactions": {
                "name": "Number of interactions to include",
                "value": 5,
                "component": "number",
                "info": "The maximum number of chat interactions to include in the LLM",
            },
            "trigger_context": {
                "name": "Maximum message length for context rewriting",
                "value": 150,
                "component": "number",
                "info": (
                    "The maximum length of the message to trigger context addition. "
                    "Exceeding this length, the message will be used as is."
                ),
            },
        }

    @classmethod
    def get_info(cls) -> dict:
        return {
            "id": "simple",
            "name": "Simple QA",
            "description": (
                "Simple RAG-based question answering pipeline. This pipeline can "
                "perform both keyword search and similarity search to retrieve the "
                "context. After that it includes that context to generate the answer."
            ),
        }


class FullDecomposeQAPipeline(FullQAPipeline):
    def answer_sub_questions(
        self, messages: list, conv_id: str, history: list, **kwargs
    ):
        output_str = ""
        for idx, message in enumerate(messages):
            yield Document(
                channel="chat",
                content=f"<br><b>Sub-question {idx + 1}</b>"
                f"<br>{message}<br><b>Answer</b><br>",
            )
            # should populate the context
            docs, infos = self.retrieve(message, history)
            print(f"Got {len(docs)} retrieved documents")

            yield from infos

            refused = abstain_events(message, docs)
            if refused:
                print("Refusing to answer a sub-question: evidence too weak")
                yield from refused
                output_str += (
                    f"Sub-question {idx + 1}-th: '{message}'\nAnswer: (refused)\n\n"
                )
                continue

            evidence_mode, evidence, images = self.evidence_pipeline(docs).content
            answer = yield from self.answering_pipeline.stream(
                question=message,
                history=history,
                evidence=evidence,
                evidence_mode=evidence_mode,
                images=images,
                conv_id=conv_id,
                **kwargs,
            )

            output_str += (
                f"Sub-question {idx + 1}-th: '{message}'\nAnswer: '{answer.text}'\n\n"
            )

        return output_str

    def stream(  # type: ignore
        self, message: str, conv_id: str, history: list, **kwargs  # type: ignore
    ) -> Generator[Document, None, Document]:
        sub_question_answer_output = ""
        if self.rewrite_pipeline:
            print("Chosen rewrite pipeline", self.rewrite_pipeline)
            result = self.rewrite_pipeline(question=message)
            print("Rewrite result", result)
            if isinstance(result, Document):
                message = result.text
            elif (
                isinstance(result, list)
                and len(result) > 0
                and isinstance(result[0], Document)
            ):
                yield Document(
                    channel="chat",
                    content="<h4>Sub questions and their answers</h4>",
                )
                sub_question_answer_output = yield from self.answer_sub_questions(
                    [r.text for r in result], conv_id, history, **kwargs
                )

        yield Document(
            channel="chat",
            content=f"<h4>Main question</h4>{message}<br><b>Answer</b><br>",
        )

        # should populate the context
        docs, infos = self.retrieve(message, history)
        print(f"Got {len(docs)} retrieved documents")
        yield from infos

        refused = abstain_events(message, docs)
        if refused:
            print("Refusing to answer the main question: evidence too weak")
            yield Document(channel="evidence", content=self.structured_evidence(None, docs))
            yield from refused
            return Document(text=refused[-1].content, channel="chat")

        evidence_mode, evidence, images = self.evidence_pipeline(docs).content
        answer = yield from self.answering_pipeline.stream(
            question=message,
            history=history,
            evidence=evidence + "\n" + sub_question_answer_output,
            evidence_mode=evidence_mode,
            images=images,
            conv_id=conv_id,
            **kwargs,
        )

        # show the evidence
        with_citation, without_citation = self.answering_pipeline.prepare_citations(
            answer, docs
        )
        yield Document(channel="evidence", content=self.structured_evidence(answer, docs))
        if not with_citation and not without_citation:
            yield Document(
                channel="info",
                content=Render.empty_state(
                    tr("No evidence yet"),
                    tr("Evidence will appear here after you ask a question."),
                ),
            )
        else:
            yield Document(channel="info", content=None)
            yield from with_citation
            yield from without_citation

        return answer

    @classmethod
    def get_user_settings(cls) -> dict:
        user_settings = super().get_user_settings()
        user_settings["decompose_prompt"] = {
            "name": "Decompose Prompt",
            "value": DecomposeQuestionPipeline.DECOMPOSE_SYSTEM_PROMPT_TEMPLATE,
        }
        return user_settings

    @classmethod
    def prepare_pipeline_instance(cls, settings, retrievers):
        prefix = f"reasoning.options.{cls.get_info()['id']}"
        pipeline = cls(
            retrievers=retrievers,
            rewrite_pipeline=DecomposeQuestionPipeline(
                prompt_template=settings.get(f"{prefix}.decompose_prompt")
            ),
        )
        return pipeline

    @classmethod
    def get_info(cls) -> dict:
        return {
            "id": "complex",
            "name": "Complex QA",
            "description": (
                "Use multi-step reasoning to decompose a complex question into "
                "multiple sub-questions. This pipeline can "
                "perform both keyword search and similarity search to retrieve the "
                "context. After that it includes that context to generate the answer."
            ),
        }
