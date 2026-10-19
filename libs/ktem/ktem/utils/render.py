import logging
import os

import markdown
from fast_langdetect import detect

from kotaemon.base import RetrievedDocument

from .i18n import tr

BASE_PATH = os.environ.get("GR_FILE_ROOT_PATH", "")

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str | None:
    """Language code of ``text``, tolerant of the detector's return shape.

    ``fast_langdetect.detect`` returns a **list** such as ``[{"lang": "zh", ...}]``.
    Indexing it with ``["lang"]`` raised ``TypeError`` on every citation preview, so the
    bare ``except`` printed the message and fell back — the language-aware branch never
    ran and every answer logged a few "list indices must be integers" lines
    (MODIFICATIONS §5.19).

    Returns ``None`` when detection fails; callers then treat the text as untagged.
    """
    try:
        result = detect(text)
    except Exception as exc:  # noqa: BLE001 - detection is best effort
        logger.warning("could not detect the language of a citation: %s", exc)
        return None

    if isinstance(result, dict):
        return result.get("lang")
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return result[0].get("lang")
    return None


def is_close(val1, val2, tolerance=1e-9):
    return abs(val1 - val2) <= tolerance


def replace_mardown_header(text: str) -> str:
    textlines = text.splitlines()
    newlines = []
    for line in textlines:
        if line.startswith("#"):
            line = "<strong>" + line.replace("#", "") + "</strong>"
        if line.startswith("=="):
            line = ""
        newlines.append(line)

    return "\n".join(newlines)


def get_header(doc: RetrievedDocument) -> str:
    """Get the header for the document"""
    header = ""
    if "page_label" in doc.metadata:
        header += " " + tr("[Page {}]").format(doc.metadata["page_label"])

    header += f" {doc.metadata.get('file_name', '<evidence>')}"
    return header.strip()


def _number(value) -> float:
    """A metadata score as a float; 0.0 for anything missing or malformed."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def has_rerank_score(doc: RetrievedDocument) -> bool:
    """Whether a reranker scored this chunk (even if the score is 0.0)."""
    metadata = getattr(doc, "metadata", None) or {}
    return any(
        metadata.get(key) is not None for key in ("reranking_score", "rerank_score")
    )


def reranking_score_of(doc: RetrievedDocument) -> float:
    """The reranker's score: Cohere/Voyage/tei write ``reranking_score``, the local
    lexical reranker writes ``rerank_score``.

    Reading only the first key made the evidence panel show ``[得分: 0.0]`` and
    ``相关性分数: 0.0`` for every chunk whenever the local reranker was the configured
    one — the panel claimed zero relevance for chunks the reranker had ranked, so a
    retrieval miss was indistinguishable from an empty store (MODIFICATIONS §5.21).
    """
    metadata = getattr(doc, "metadata", None) or {}
    for key in ("reranking_score", "rerank_score"):
        if metadata.get(key) is not None:
            return round(_number(metadata[key]), 2)
    return 0.0


def relevance_score_of(doc: RetrievedDocument) -> float:
    """The score the evidence panel calls relevance: what actually ranked this chunk.

    The LLM judge wins when it ran (it is the only one that read the answer), then the
    reranker — **including a 0.0**, because that is the reranker's verdict — then the
    vector similarity when no reranker ran at all.

    Falling back from a 0.0 rerank score to the vector similarity mixed two scales: a
    chunk the reranker had rejected (0.0) was shown a 0.31 similarity while the chunk
    that matched the question was shown 0.29, so relevant and unrelated chunks looked
    the same (MODIFICATIONS §5.23).
    """
    metadata = getattr(doc, "metadata", None) or {}
    llm_score = _number(metadata.get("llm_trulens_score"))
    if llm_score > 0:
        return round(llm_score, 2)
    if has_rerank_score(doc):
        return reranking_score_of(doc)
    similarity = _number(getattr(doc, "score", 0.0))
    return round(similarity, 2) if similarity > 0 else 0.0


class Render:
    """Default text rendering into HTML for the UI"""

    @staticmethod
    def collapsible(header, content, open: bool = False) -> str:
        """Render an HTML friendly collapsible section"""
        o = " open" if open else ""
        return (
            f"<details class='evidence' {o}><summary>"
            f"{header}</summary>{content}"
            "</details><br>"
        )

    @staticmethod
    def empty_state(title: str, hint: str = "") -> str:
        """Render the placeholder shown by a panel that has nothing to display yet.

        Used by the information panel before the first answer (and when an answer
        carried no evidence), so an empty panel explains itself instead of
        appearing broken.
        """
        hint_html = f'<div class="empty-state-hint">{hint}</div>' if hint else ""
        return (
            '<div class="empty-state">'
            f'<div class="empty-state-title">{title}</div>'
            f"{hint_html}"
            "</div>"
        )

    @staticmethod
    def table(text: str) -> str:
        """Render table from markdown format into HTML"""
        text = replace_mardown_header(text)
        return markdown.markdown(
            text,
            extensions=[
                "markdown.extensions.tables",
                "markdown.extensions.fenced_code",
            ],
        )

    @staticmethod
    def table_preserve_linebreaks(text: str) -> str:
        """Render table from markdown format into HTML"""
        return markdown.markdown(
            text,
            extensions=[
                "markdown.extensions.tables",
                "markdown.extensions.fenced_code",
            ],
        ).replace("\n", "<br>")

    @staticmethod
    def preview(
        html_content: str,
        doc: RetrievedDocument,
        highlight_text: str | None = None,
    ) -> str:
        text = doc.content
        pdf_path = doc.metadata.get("file_path", "")

        # Only PDFs get the inline preview, so only a PDF is worth a warning when its
        # file is gone: the stored copy of a non-PDF is never opened in the viewer, and
        # warning on every citation made the log useless (MODIFICATIONS §5.12).
        is_pdf = doc.metadata.get("file_type", "") == "application/pdf"
        if not is_pdf:
            return html_content

        if not os.path.isfile(pdf_path):
            print(f"pdf-path: {pdf_path} does not exist")
            return html_content

        page_idx = int(doc.metadata.get("page_label", 1))

        if page_idx < 0:
            print("Fail to extract page number")
            return html_content

        if not highlight_text:
            phrase = "false"
            try:
                # the detector returns a list; asking it for ["lang"] raised on every
                # preview and the bare except hid it (MODIFICATIONS §5.19)
                lang = detect_language(text.replace("\n", " "))
                if lang not in ["ja", "cn", "zh"]:
                    highlight_words = [
                        t[:-1] if t.endswith("-") else t for t in text.split("\n")
                    ]
                    highlight_text = highlight_words[0]
                    phrase = "true"

                highlight_text = (
                    text.replace("\n", "").replace('"', "").replace("'", "")
                )
            except Exception as exc:  # noqa: BLE001 - the link is still usable
                logger.warning("could not build the citation highlight: %s", exc)
                highlight_text = text
        else:
            phrase = "true"

        return f"""
        {html_content}
        <a href="#" class="pdf-link" data-src="{BASE_PATH}/file={pdf_path}" data-page="{page_idx}" data-search="{highlight_text}" data-phrase="{phrase}">
            [{tr('Preview')}]
        </a>
        """  # noqa

    @staticmethod
    def highlight(text: str, elem_id: str | None = None) -> str:
        """Highlight text"""
        id_text = f" id='mark-{elem_id}'" if elem_id else ""
        return f"<mark{id_text}>{text}</mark>"

    @staticmethod
    def image(url: str, text: str = "") -> str:
        """Render an image"""
        img = f'<img src="{url}"><br>'
        if text:
            caption = f"<p>{text}</p>"
            return f"<figure>{img}{caption}</figure><br>"
        return img

    @staticmethod
    def collapsible_with_header(
        doc: RetrievedDocument,
        open_collapsible: bool = False,
    ) -> str:
        header = f"<i>{get_header(doc)}</i>"
        if doc.metadata.get("type", "") == "image":
            doc_content = Render.image(url=doc.metadata["image_origin"], text=doc.text)
        elif doc.metadata.get("type", "") == "table_raw":
            doc_content = Render.table_preserve_linebreaks(doc.text)
        else:
            doc_content = Render.table(doc.text)

        return Render.collapsible(
            header=Render.preview(header, doc),
            content=doc_content,
            open=open_collapsible,
        )

    @staticmethod
    def collapsible_with_header_score(
        doc: RetrievedDocument,
        override_text: str | None = None,
        highlight_text: str | None = None,
        open_collapsible: bool = False,
    ) -> str:
        """Format the retrieval score and the document"""
        # score from doc_store (Elasticsearch)
        if is_close(doc.score, -1.0):
            vectorstore_score = ""
            text_search_str = f" ({tr('full-text search')})<br>"
        else:
            vectorstore_score = str(round(doc.score, 2))
            text_search_str = "<br>"

        llm_reranking_score = round(_number(doc.metadata.get("llm_trulens_score")), 2)
        reranking_score = reranking_score_of(doc)
        item_type = doc.metadata.get("type", "").capitalize()
        item_type_prefix = f"{item_type} from " if item_type else ""

        if "raw" in item_type_prefix:
            item_type_prefix = ""
        elif item_type_prefix:
            # the space is added here: a translation is stripped by clean_translation
            item_type_prefix = tr("{} from").format(tr(item_type)) + " "

        relevant_score = relevance_score_of(doc)

        rendered_score = Render.collapsible(
            header=f"<b>&emsp;{tr('Relevance score')}</b>: {relevant_score:.1f}",
            content=f"<b>&emsp;&emsp;{tr('Vectorstore score:')}</b>"
            f" {vectorstore_score}"
            f"{text_search_str}"
            f"<b>&emsp;&emsp;{tr('LLM relevant score:')}</b>"
            f" {llm_reranking_score}<br>"
            f"<b>&emsp;&emsp;{tr('Reranking score:')}</b>"
            f" {reranking_score}<br>",
        )

        text = doc.text if not override_text else override_text
        if doc.metadata.get("type", "") == "image":
            rendered_doc_content = Render.image(
                url=doc.metadata["image_origin"],
                text=text,
            )
        elif doc.metadata.get("type", "") == "table_raw":
            rendered_doc_content = Render.table_preserve_linebreaks(doc.text)
        else:
            rendered_doc_content = Render.table(text)

        # The relevance value stays inside the summary: that is the only number the
        # collapsed row shows, and the evidence tests read it from there. It is a
        # chip now (label + value) so the number cannot be mistaken for part of the
        # file name printed next to it.
        chip = (
            '<span class="chip">'
            f'<span class="chip-label">{tr("Relevance score")}</span>'
            f'<span class="chip-value">{relevant_score}</span>'
            "</span>"
        )
        rendered_header = Render.preview(
            f'<span class="meta"><i>{item_type_prefix}{get_header(doc)}</i></span>'
            f"{chip}",
            doc,
            highlight_text=highlight_text,
        )
        rendered_doc_content = (
            f"<div class='evidence-content'>{rendered_doc_content}</div>"
        )

        return Render.collapsible(
            header=rendered_header,
            content=rendered_score + rendered_doc_content,
            open=open_collapsible,
        )
