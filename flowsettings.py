import os
from importlib.metadata import version
from inspect import currentframe, getframeinfo
from pathlib import Path

from decouple import config
from ktem.utils.lang import SUPPORTED_LANGUAGE_MAP
from theflow.settings.default import *  # noqa

cur_frame = currentframe()
if cur_frame is None:
    raise ValueError("Cannot get the current frame.")
this_file = getframeinfo(cur_frame).filename
this_dir = Path(this_file).parent

# change this if your app use a different name
KH_PACKAGE_NAME = "kotaemon_app"
# Display name shown in the window title, sidebar and login/help pages.
KH_APP_NAME = config("KH_APP_NAME", default="citeask")

KH_APP_VERSION = config("KH_APP_VERSION", None)
if not KH_APP_VERSION:
    try:
        # Caution: This might produce the wrong version
        # https://stackoverflow.com/a/59533071
        KH_APP_VERSION = version(KH_PACKAGE_NAME)
    except Exception:
        KH_APP_VERSION = "local"

KH_GRADIO_SHARE = config("KH_GRADIO_SHARE", default=False, cast=bool)
# The React application is the default UI (served at `/`, with the classic Gradio
# app at `/legacy`). Set KH_WEB_UI=0 to go back to serving only Gradio at `/` -
# the rollback switch for the front-end migration (MODIFICATIONS §5.25).
KH_WEB_UI = config("KH_WEB_UI", default=True, cast=bool)
# Signing key of the web session cookie. Empty = a random key persisted under
# ktem_app_data/session.key on first start.
KH_SESSION_SECRET = config("KH_SESSION_SECRET", default="")
# Open the browser when the app finishes starting. The Windows launcher sets this to 0
# and opens the page itself once the port answers 200 — opening too early lands on a
# "connection refused" tab, and on some hosts `webbrowser.open` does nothing at all
# (MODIFICATIONS 5.6). Direct `python app.py` keeps the old behaviour.
KH_OPEN_BROWSER_ON_START = config("KH_OPEN_BROWSER_ON_START", default=True, cast=bool)
KH_ENABLE_FIRST_SETUP = config("KH_ENABLE_FIRST_SETUP", default=True, cast=bool)
KH_DEMO_MODE = config("KH_DEMO_MODE", default=False, cast=bool)
KH_OLLAMA_URL = config("KH_OLLAMA_URL", default="http://localhost:11434/v1/")

# App can be ran from anywhere and it's not trivial to decide where to store app data.
# So let's use the same directory as the flowsetting.py file.
KH_APP_DATA_DIR = this_dir / "ktem_app_data"
KH_APP_DATA_EXISTS = KH_APP_DATA_DIR.exists()
KH_APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

# User data directory
KH_USER_DATA_DIR = KH_APP_DATA_DIR / "user_data"
KH_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# markdown output directory
KH_MARKDOWN_OUTPUT_DIR = KH_APP_DATA_DIR / "markdown_cache_dir"
KH_MARKDOWN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# chunks output directory
KH_CHUNKS_OUTPUT_DIR = KH_APP_DATA_DIR / "chunks_cache_dir"
KH_CHUNKS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# zip output directory
KH_ZIP_OUTPUT_DIR = KH_APP_DATA_DIR / "zip_cache_dir"
KH_ZIP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# zip input directory
KH_ZIP_INPUT_DIR = KH_APP_DATA_DIR / "zip_cache_dir_in"
KH_ZIP_INPUT_DIR.mkdir(parents=True, exist_ok=True)

# HF models can be big, let's store them in the app data directory so that it's easier
# for users to manage their storage.
# ref: https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache
os.environ["HF_HOME"] = str(KH_APP_DATA_DIR / "huggingface")
os.environ["HF_HUB_CACHE"] = str(KH_APP_DATA_DIR / "huggingface")

# FastEmbed caches its ONNX models under `tempfile.gettempdir()` by default. That
# location changes when TMP is redirected (e.g. inside a sandbox) and can be wiped
# by cleanup tools, which would re-download a ~1GB model. Pin it to app data.
os.environ.setdefault("FASTEMBED_CACHE_PATH", str(KH_APP_DATA_DIR / "fastembed_cache"))

# doc directory
KH_DOC_DIR = this_dir / "docs"

KH_MODE = "dev"
# UI language for the Gradio front-end. This fork defaults to Simplified Chinese
# ("zh"); set KH_UI_LANGUAGE=en to get the original upstream strings back.
KH_UI_LANGUAGE = config("KH_UI_LANGUAGE", default="zh")
# Where the UI translations come from. Translations are produced at build time by
# `deep_translator` (or by the chat model) and cached in
# ktem_app_data/i18n/<lang>.json, so they are generated instead of hard-coded.
# Backends: llm (default, reuses the configured chat model and preserves
# Markdown), mymemory, google, libre. See MODIFICATIONS.md §3 for measurements.
KH_UI_TRANSLATOR = config("KH_UI_TRANSLATOR", default="llm")
# Translate strings missing from the catalog while starting up. Off by default:
# the free services need ~2s per string, so building the catalog is an explicit
# step (`python -m ktem.utils.i18n build`) and startup only reads the cache.
KH_UI_TRANSLATE_MISSING = config("KH_UI_TRANSLATE_MISSING", default=False, cast=bool)
# Language the chat model is asked to answer in. It follows the UI language by
# default: the QA prompt ends with "Give answer in {lang}", so this single value
# is what keeps the answers from being English on a Chinese UI. Override with the
# Language dropdown in the chat settings, or set KH_ANSWER_LANGUAGE=en.
KH_ANSWER_LANGUAGE = config(
    "KH_ANSWER_LANGUAGE",
    default=KH_UI_LANGUAGE if KH_UI_LANGUAGE in SUPPORTED_LANGUAGE_MAP else "en",
)
KH_SSO_ENABLED = config("KH_SSO_ENABLED", default=False, cast=bool)

KH_FEATURE_CHAT_SUGGESTION = config(
    "KH_FEATURE_CHAT_SUGGESTION", default=False, cast=bool
)
KH_FEATURE_USER_MANAGEMENT = config(
    "KH_FEATURE_USER_MANAGEMENT", default=True, cast=bool
)
KH_USER_CAN_SEE_PUBLIC = None
KH_FEATURE_USER_MANAGEMENT_ADMIN = str(
    config("KH_FEATURE_USER_MANAGEMENT_ADMIN", default="admin")
)
KH_FEATURE_USER_MANAGEMENT_PASSWORD = str(
    config("KH_FEATURE_USER_MANAGEMENT_PASSWORD", default="admin")
)
KH_ENABLE_ALEMBIC = False
KH_DATABASE = f"sqlite:///{KH_USER_DATA_DIR / 'sql.db'}"
KH_FILESTORAGE_PATH = str(KH_USER_DATA_DIR / "files")
# Re-parse, at startup, the files that are listed in the index but have no chunks
# (a parse that failed before its reader was fixed — MODIFICATIONS §2.7/§2.9/§2.10).
# Runs in a background thread; re-embedding a 10 MB spreadsheet takes minutes, so
# set to False if the machine must not spend that much at boot.
KH_REPAIR_ORPHAN_FILES = config("KH_REPAIR_ORPHAN_FILES", default=True, cast=bool)
# Chunking granularity (ROADMAP B3). Left at 0 the index keeps one chunk per page,
# which is coarse for long pages; setting 512/64 splits by token instead. The
# measured A/B is in MODIFICATIONS §5.7 — set 0 here to fall back to page chunks.
# Changing this only affects files indexed afterwards: re-run
# `python tools/reindex_corpus.py` to apply it to an existing corpus.
FILE_INDEX_PIPELINE_SPLITTER_CHUNK_SIZE = config(
    "FILE_INDEX_PIPELINE_SPLITTER_CHUNK_SIZE", default=512, cast=int
)
FILE_INDEX_PIPELINE_SPLITTER_CHUNK_OVERLAP = config(
    "FILE_INDEX_PIPELINE_SPLITTER_CHUNK_OVERLAP", default=64, cast=int
)
# Refusal gate (ROADMAP B4): when the best retrieval score is below this, the chat
# page says "the knowledge base has no evidence" instead of letting the model answer
# from its own memory. Threshold calibrated on tools/eval/zh-no-answer.json — the
# measurement is in MODIFICATIONS §5.8; 0 disables the gate (only "nothing retrieved"
# is refused, which was the old behaviour).
KH_ABSTAIN_SCORE_THRESHOLD = config(
    "KH_ABSTAIN_SCORE_THRESHOLD", default=0.45, cast=float
)
# A rare entity term (a name in a table row, an id) in a retrieved chunk lowers the bar
# to this floor: a dense spreadsheet row answers correctly far below the prose threshold
# (MODIFICATIONS 5.8). Set to 0 to disable the override.
KH_ABSTAIN_TERM_FLOOR = config("KH_ABSTAIN_TERM_FLOOR", default=0.33, cast=float)
# Per-file retrieval: keep the best chunk of every file before the second chunk of any
# file, so one large spreadsheet cannot take every context slot (MODIFICATIONS 5.13).
KH_RETRIEVAL_PER_FILE = config("KH_RETRIEVAL_PER_FILE", default=True, cast=bool)
# How many candidates per slot to fetch before the per-file pass (3 = 3x top_k).
KH_RETRIEVAL_CANDIDATES = config("KH_RETRIEVAL_CANDIDATES", default=3, cast=int)
# A file that the global ranking left out gets its own query, up to this many files, and
# contributes this many chunks (each extra query costs one embedding call).
KH_RETRIEVAL_MAX_FILES = config("KH_RETRIEVAL_MAX_FILES", default=8, cast=int)
KH_RETRIEVAL_PER_FILE_K = config("KH_RETRIEVAL_PER_FILE_K", default=3, cast=int)
# File routing: every indexed file keeps a short profile ("文件：… 内容摘录：…") in
# Source.note["summary"]; a question is then routed to the few closest files instead of
# searching the whole selection (MODIFICATIONS 5.14).
KH_FILE_ROUTING = config("KH_FILE_ROUTING", default=True, cast=bool)
KH_FILE_ROUTING_TOP_M = config("KH_FILE_ROUTING_TOP_M", default=3, cast=int)
KH_FILE_ROUTING_MIN_SIMILARITY = config(
    "KH_FILE_ROUTING_MIN_SIMILARITY", default=0.30, cast=float
)
# A file is kept when its profile scores at least this share of the best one, so a
# specific question is routed to a single file while an ambiguous one keeps near-ties.
KH_FILE_ROUTING_MIN_RATIO = config(
    "KH_FILE_ROUTING_MIN_RATIO", default=0.80, cast=float
)
# A profile says what a file is *about*, not who is *in* it: a grades spreadsheet whose
# rows name the queried student can fall below the relative cut. Files whose full-text
# hits name the entity in a table are added back (MODIFICATIONS 5.20). One full-text
# query, no embedding; 0 disables the lookup.
KH_ROUTING_ENTITY_FILES = config("KH_ROUTING_ENTITY_FILES", default=2, cast=int)
KH_ROUTING_ENTITY_CANDIDATES = config(
    "KH_ROUTING_ENTITY_CANDIDATES", default=30, cast=int
)
# A 10k-chunk spreadsheet added to the search scope takes over the candidate list even
# when one of its rows holds the answer (MODIFICATIONS 5.13/5.20), so entity routing
# only adds files below this many chunks; 0 means "any size".
KH_ROUTING_ENTITY_MAX_CHUNKS = config(
    "KH_ROUTING_ENTITY_MAX_CHUNKS", default=500, cast=int
)
# Entity row lookup: a question that names one person is a *row* lookup, and the row is
# not what a vector query ranks first (the rules notice scores 0.58, the row 0.35), so
# the chunk that names the entity is promoted into the context instead of being ranked
# for. A row identifier is a term that occupies a table *cell* (never prose, and never
# an award column that repeats down a chunk); 0 disables the pass (MODIFICATIONS 5.21).
KH_ENTITY_ROWS = config("KH_ENTITY_ROWS", default=3, cast=int)
# Optional cap on how many full-text chunks may carry the identifier (0 = no cap: a
# student who appears in ten tables is still a row identifier; KH_ENTITY_ROWS already
# bounds how many chunks are promoted).
KH_ENTITY_ROW_MAX_CHUNKS = config(
    "KH_ENTITY_ROW_MAX_CHUNKS", default=0, cast=int
)
# Per-query trace (ROADMAP C4): one JSON line per question with retrieved count, best
# similarity, refusal flag, latency and the LLM usage that request consumed. Empty =
# off; "1" = <app data>/query_trace.jsonl; anything else is used as the path. Read it
# with `python tools/trace_report.py`.
KH_QUERY_TRACE = config("KH_QUERY_TRACE", default="")
KH_WEB_SEARCH_BACKEND = (
    "kotaemon.indices.retrievers.tavily_web_search.WebSearch"
    # "kotaemon.indices.retrievers.jina_web_search.WebSearch"
)

KH_DOCSTORE = {
    # "__type__": "kotaemon.storages.ElasticsearchDocumentStore",
    # "__type__": "kotaemon.storages.SimpleFileDocumentStore",
    "__type__": "kotaemon.storages.LanceDBDocumentStore",
    "path": str(KH_USER_DATA_DIR / "docstore"),
}
KH_VECTORSTORE = {
    # "__type__": "kotaemon.storages.LanceDBVectorStore",
    "__type__": "kotaemon.storages.ChromaVectorStore",
    # "__type__": "kotaemon.storages.MilvusVectorStore",
    # "__type__": "kotaemon.storages.QdrantVectorStore",
    "path": str(KH_USER_DATA_DIR / "vectorstore"),
}
KH_LLMS = {}
KH_EMBEDDINGS = {}
KH_RERANKINGS = {}

# populate options from config
if config("AZURE_OPENAI_API_KEY", default="") and config(
    "AZURE_OPENAI_ENDPOINT", default=""
):
    if config("AZURE_OPENAI_CHAT_DEPLOYMENT", default=""):
        KH_LLMS["azure"] = {
            "spec": {
                "__type__": "kotaemon.llms.AzureChatOpenAI",
                "temperature": 0,
                "azure_endpoint": config("AZURE_OPENAI_ENDPOINT", default=""),
                "api_key": config("AZURE_OPENAI_API_KEY", default=""),
                "api_version": config("OPENAI_API_VERSION", default="")
                or "2024-02-15-preview",
                "azure_deployment": config("AZURE_OPENAI_CHAT_DEPLOYMENT", default=""),
                "timeout": 20,
            },
            "default": False,
        }
    if config("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", default=""):
        KH_EMBEDDINGS["azure"] = {
            "spec": {
                "__type__": "kotaemon.embeddings.AzureOpenAIEmbeddings",
                "azure_endpoint": config("AZURE_OPENAI_ENDPOINT", default=""),
                "api_key": config("AZURE_OPENAI_API_KEY", default=""),
                "api_version": config("OPENAI_API_VERSION", default="")
                or "2024-02-15-preview",
                "azure_deployment": config(
                    "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", default=""
                ),
                "timeout": 10,
            },
            "default": False,
        }

OPENAI_DEFAULT = "<YOUR_OPENAI_KEY>"
OPENAI_API_KEY = config("OPENAI_API_KEY", default=OPENAI_DEFAULT)
GOOGLE_API_KEY = config("GOOGLE_API_KEY", default="your-key")
IS_OPENAI_DEFAULT = len(OPENAI_API_KEY) > 0 and OPENAI_API_KEY != OPENAI_DEFAULT

if OPENAI_API_KEY:
    KH_LLMS["openai"] = {
        "spec": {
            "__type__": "kotaemon.llms.ChatOpenAI",
            "temperature": 0,
            "base_url": config("OPENAI_API_BASE", default="")
            or "https://api.openai.com/v1",
            "api_key": OPENAI_API_KEY,
            "model": config("OPENAI_CHAT_MODEL", default="gpt-4o-mini"),
            "timeout": 20,
        },
        "default": IS_OPENAI_DEFAULT,
    }
    KH_EMBEDDINGS["openai"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
            "base_url": config("OPENAI_API_BASE", default="https://api.openai.com/v1"),
            "api_key": OPENAI_API_KEY,
            "model": config(
                "OPENAI_EMBEDDINGS_MODEL", default="text-embedding-3-large"
            ),
            "timeout": 10,
            "context_length": 8191,
        },
        "default": IS_OPENAI_DEFAULT,
    }

VOYAGE_API_KEY = config("VOYAGE_API_KEY", default="")
if VOYAGE_API_KEY:
    KH_EMBEDDINGS["voyageai"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.VoyageAIEmbeddings",
            "api_key": VOYAGE_API_KEY,
            "model": config("VOYAGE_EMBEDDINGS_MODEL", default="voyage-3-large"),
        },
        "default": False,
    }
    KH_RERANKINGS["voyageai"] = {
        "spec": {
            "__type__": "kotaemon.rerankings.VoyageAIReranking",
            "model_name": "rerank-2",
            "api_key": VOYAGE_API_KEY,
        },
        "default": False,
    }

if config("LOCAL_MODEL", default=""):
    KH_LLMS["ollama"] = {
        "spec": {
            "__type__": "kotaemon.llms.ChatOpenAI",
            "base_url": KH_OLLAMA_URL,
            "model": config("LOCAL_MODEL", default="qwen2.5:7b"),
            "api_key": "ollama",
        },
        "default": False,
    }
    KH_LLMS["ollama-long-context"] = {
        "spec": {
            "__type__": "kotaemon.llms.LCOllamaChat",
            "base_url": KH_OLLAMA_URL.replace("v1/", ""),
            "model": config("LOCAL_MODEL", default="qwen2.5:7b"),
            "num_ctx": 8192,
        },
        "default": False,
    }

    KH_EMBEDDINGS["ollama"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
            "base_url": KH_OLLAMA_URL,
            "model": config("LOCAL_MODEL_EMBEDDINGS", default="nomic-embed-text"),
            "api_key": "ollama",
        },
        "default": False,
    }
    KH_EMBEDDINGS["fast_embed"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.FastEmbedEmbeddings",
            "model_name": "BAAI/bge-base-en-v1.5",
        },
        "default": False,
    }

# additional LLM configurations
KH_LLMS["claude"] = {
    "spec": {
        "__type__": "kotaemon.llms.chats.LCAnthropicChat",
        "model_name": "claude-3-5-sonnet-20240620",
        "api_key": "your-key",
    },
    "default": False,
}
KH_LLMS["google"] = {
    "spec": {
        "__type__": "kotaemon.llms.chats.LCGeminiChat",
        "model_name": "gemini-1.5-flash",
        "api_key": GOOGLE_API_KEY,
    },
    "default": not IS_OPENAI_DEFAULT,
}
KH_LLMS["groq"] = {
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.1-8b-instant",
        "api_key": "your-key",
    },
    "default": False,
}
KH_LLMS["cohere"] = {
    "spec": {
        "__type__": "kotaemon.llms.chats.LCCohereChat",
        "model_name": "command-r-plus-08-2024",
        "api_key": config("COHERE_API_KEY", default="your-key"),
    },
    "default": False,
}
KH_LLMS["mistral"] = {
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "base_url": "https://api.mistral.ai/v1",
        "model": "ministral-8b-latest",
        "api_key": config("MISTRAL_API_KEY", default="your-key"),
    },
    "default": False,
}

# additional embeddings configurations
KH_EMBEDDINGS["cohere"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.LCCohereEmbeddings",
        "model": "embed-multilingual-v3.0",
        "cohere_api_key": config("COHERE_API_KEY", default="your-key"),
        "user_agent": "default",
    },
    "default": False,
}
KH_EMBEDDINGS["google"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.LCGoogleEmbeddings",
        "model": "models/text-embedding-004",
        "google_api_key": GOOGLE_API_KEY,
    },
    "default": not IS_OPENAI_DEFAULT,
}
KH_EMBEDDINGS["mistral"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.LCMistralEmbeddings",
        "model": "mistral-embed",
        "api_key": config("MISTRAL_API_KEY", default="your-key"),
    },
    "default": False,
}
# KH_EMBEDDINGS["huggingface"] = {
#     "spec": {
#         "__type__": "kotaemon.embeddings.LCHuggingFaceEmbeddings",
#         "model_name": "sentence-transformers/all-mpnet-base-v2",
#     },
#     "default": False,
# }

# default reranking models
KH_RERANKINGS["cohere"] = {
    "spec": {
        "__type__": "kotaemon.rerankings.CohereReranking",
        "model_name": "rerank-v4.0-fast",
        "cohere_api_key": config("COHERE_API_KEY", default=""),
    },
    "default": True,
}
# Local reranker: no key, no model, no network (MODIFICATIONS §5.9). Cohere without a
# key is unusable, so the index pipeline falls back to this one — pick it here
# explicitly if you prefer it even when a Cohere key is configured.
# Note: the model pool is seeded only into an empty database, so an existing install
# lists it after re-seeding (Resources → delete the row, or rebuild the app data).
KH_RERANKINGS["local"] = {
    "spec": {"__type__": "kotaemon.rerankings.LocalLexicalReranker"},
    "default": False,
}

KH_REASONINGS = [
    "ktem.reasoning.simple.FullQAPipeline",
    "ktem.reasoning.simple.FullDecomposeQAPipeline",
    "ktem.reasoning.react.ReactAgentPipeline",
    "ktem.reasoning.rewoo.RewooAgentPipeline",
]
KH_REASONINGS_USE_MULTIMODAL = config("USE_MULTIMODAL", default=False, cast=bool)
KH_VLM_ENDPOINT = "{0}/openai/deployments/{1}/chat/completions?api-version={2}".format(
    config("AZURE_OPENAI_ENDPOINT", default=""),
    config("OPENAI_VISION_DEPLOYMENT_NAME", default="gpt-4o"),
    config("OPENAI_API_VERSION", default=""),
)


SETTINGS_APP: dict[str, dict] = {}


SETTINGS_REASONING = {
    "use": {
        "name": "Reasoning options",
        "value": None,
        "choices": [],
        "component": "radio",
    },
    "lang": {
        "name": "Language",
        "value": KH_ANSWER_LANGUAGE,
        "choices": [(lang, code) for code, lang in SUPPORTED_LANGUAGE_MAP.items()],
        "component": "dropdown",
    },
    "max_context_length": {
        "name": "Max context length (LLM)",
        "value": 32000,
        "component": "number",
    },
}

USE_GLOBAL_GRAPHRAG = config("USE_GLOBAL_GRAPHRAG", default=True, cast=bool)
USE_NANO_GRAPHRAG = config("USE_NANO_GRAPHRAG", default=False, cast=bool)
USE_LIGHTRAG = config("USE_LIGHTRAG", default=True, cast=bool)
USE_MS_GRAPHRAG = config("USE_MS_GRAPHRAG", default=True, cast=bool)

GRAPHRAG_INDEX_TYPES = []

if USE_MS_GRAPHRAG:
    GRAPHRAG_INDEX_TYPES.append("ktem.index.file.graph.GraphRAGIndex")
if USE_NANO_GRAPHRAG:
    GRAPHRAG_INDEX_TYPES.append("ktem.index.file.graph.NanoGraphRAGIndex")
if USE_LIGHTRAG:
    GRAPHRAG_INDEX_TYPES.append("ktem.index.file.graph.LightRAGIndex")

KH_INDEX_TYPES = [
    "ktem.index.file.FileIndex",
    *GRAPHRAG_INDEX_TYPES,
]

GRAPHRAG_INDICES = [
    {
        "name": graph_type.split(".")[-1].replace("Index", "")
        + " Collection",  # get last name
        "config": {
            "supported_file_types": (
                ".png, .jpeg, .jpg, .tiff, .tif, .pdf, .xls, .xlsx, .doc, .docx, "
                ".pptx, .csv, .html, .mhtml, .txt, .md, .zip"
            ),
            "private": True,
        },
        "index_type": graph_type,
    }
    for graph_type in GRAPHRAG_INDEX_TYPES
]

KH_INDICES = [
    {
        "name": "File Collection",
        "config": {
            "supported_file_types": (
                ".png, .jpeg, .jpg, .tiff, .tif, .pdf, .xls, .xlsx, .doc, .docx, "
                ".pptx, .csv, .html, .mhtml, .txt, .md, .zip"
            ),
            "private": True,
        },
        "index_type": "ktem.index.file.FileIndex",
    },
    *GRAPHRAG_INDICES,
]

# =============================================================================
# 本地部署定制：DeepSeek 对话模型 + 本地 FastEmbed 向量模型
# -----------------------------------------------------------------------------
# 上游的 provider 默认项是按 env 状态推导出来的（例如没有 OpenAI key 时
# google 会自动成为默认，且其 api_key 是占位字符串）。这里在最后显式注册
# 本地这套并压平所有 default 标记，保证默认模型唯一且可用。
#
# 注意：模型池只在首次启动、对应数据库表为空时从本文件播种
# （见 ktem/*/manager.py）。改完本文件若未生效，删除
# ktem_app_data/user_data/sql.db 后重启即可。
# =============================================================================

# ---- 对话模型：DeepSeek（OpenAI 兼容接口） ----
DEEPSEEK_API_KEY = config("DEEPSEEK_API_KEY", default="your-key")
DEEPSEEK_API_BASE = config("DEEPSEEK_API_BASE", default="https://api.deepseek.com/v1")
DEEPSEEK_CHAT_MODEL = config("DEEPSEEK_CHAT_MODEL", default="deepseek-chat")

KH_LLMS["deepseek"] = {
    "spec": {
        "__type__": "kotaemon.llms.ChatOpenAI",
        "temperature": 0,
        "base_url": DEEPSEEK_API_BASE,
        "api_key": DEEPSEEK_API_KEY,
        "model": DEEPSEEK_CHAT_MODEL,
        "timeout": 60,
    },
    "default": True,
}

# ---- 向量模型：本地 FastEmbed（无需 API key，首次使用自动下载模型） ----
# 选型依据（同一套 30 题检索评测，见 MODIFICATIONS.md §9.4）：
#   MiniLM-L12-v2  384 维  Hit@1 36.7% / MRR 0.589   ← 原默认
#   mpnet-base-v2  768 维  Hit@1 60.0% / MRR 0.739   ← 现默认（最强且无需前缀）
#   e5-large      1024 维  Hit@1 53.3% / MRR 0.683   ← 加 E5 前缀后仍不如上面
# 若换成 E5 系列，必须同时设置 query_prefix="query: " / passage_prefix="passage: "，
# 否则会明显掉分（实测 46.7% vs 53.3%）。
KH_EMBEDDINGS["fast_embed"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.FastEmbedEmbeddings",
        "model_name": config(
            "LOCAL_EMBEDDING_MODEL",
            default="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        ),
        "batch_size": 64,
    },
    "default": True,
}

# ---- 向量模型：通义（DashScope，OpenAI 兼容接口） ----
# 与本地 FastEmbed 二选一：配了 DASHSCOPE_API_KEY 就用通义（免下载，省掉约 3.7GB 本地
# 模型），没有 key 就自动回落到本地 FastEmbed。两者可随时在「资源 → 嵌入」里切换，
# 但**换了向量模型必须重建索引**（维度不同），见 tools/reindex_corpus.py。
DASHSCOPE_API_KEY = config("DASHSCOPE_API_KEY", default="")
DASHSCOPE_API_BASE = config(
    "DASHSCOPE_API_BASE", default="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
KH_EMBEDDINGS["dashscope"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
        "base_url": DASHSCOPE_API_BASE,
        "api_key": DASHSCOPE_API_KEY,
        "model": config("DASHSCOPE_EMBEDDING_MODEL", default="text-embedding-v3"),
        # 通义单次请求的文本条数上限，实测是 10（文档写 25，接口会 400 报
        # "batch size is invalid, it should not be larger than 10"）。这里给对的值，
        # 客户端也会在服务端报错时自动采用它报出的上限，见
        # kotaemon/embeddings/openai.py::BaseOpenAIEmbeddings._smaller_batch_size
        "batch_size": 10,
    },
    "default": False,
}

# ---- 压平默认项：配了通义 key 走通义，否则走本地 FastEmbed ----
for _name, _cfg in KH_LLMS.items():
    _cfg["default"] = _name == "deepseek"
_DEFAULT_EMBEDDING = "dashscope" if DASHSCOPE_API_KEY else "fast_embed"
for _name, _cfg in KH_EMBEDDINGS.items():
    _cfg["default"] = _name == _DEFAULT_EMBEDDING
