# 对 kotaemon 上游项目的修改记录

> 本文档记录本仓库相对于上游 [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon) 的**全部改动**，
> 包括每处改动的动机、定位过程与验证证据，供后续整理简历与面试叙述使用。
>
> **基线版本**：`v0.12.0`（commit `9ad3e4e`，上游 main 分支）
> 文中的人名、机构名与文件名均为化名/示例，不代表真实数据。

---

## 一、总体改动一览

### 已跟踪文件的修改（21 个文件，+395 −59 行；§2.9/§2.10 的读取器与自愈修复另计 11 个文件 +393 −29 行；§5.4–5.6 的评测/自检/启动工具另计 4 个文件 +350 −33 行，新增路径见 §二各小节）

| 文件 | 类型 | 说明 |
|---|---|---|
| [libs/ktem/ktem/index/file/ui.py](libs/ktem/ktem/index/file/ui.py) | **缺陷修复** | 修复默认配置下检索被静默跳过；运行时提示接入翻译 |
| [libs/ktem/ktem/index/file/index.py](libs/ktem/ktem/index/file/index.py) | **缺陷修复** | 向选择器传递权威 user_id |
| [libs/ktem/ktem/pages/chat/__init__.py](libs/ktem/ktem/pages/chat/__init__.py) | **缺陷修复** | 同上 |
| [libs/ktem/ktem/index/file/graph/graph_index.py](libs/ktem/ktem/index/file/graph/graph_index.py) | **缺陷修复** | 同上（GraphRAG 分支） |
| [libs/ktem/ktem/index/file/graph/light_graph_index.py](libs/ktem/ktem/index/file/graph/light_graph_index.py) | **缺陷修复** | 同上 |
| [libs/ktem/ktem/index/file/graph/nano_graph_index.py](libs/ktem/ktem/index/file/graph/nano_graph_index.py) | **缺陷修复** | 同上 |
| [app.py](app.py) | **功能新增** | 启动时装载词条缓存、激活运行时翻译、注入 JS 词表 |
| [libs/ktem/ktem/utils/render.py](libs/ktem/ktem/utils/render.py) | **功能新增** | 引用块标签（页码 / 得分 / 类型 / 预览）接入运行时翻译 |
| [libs/ktem/ktem/assets/js/main.js](libs/ktem/ktem/assets/js/main.js) | **功能新增** | 浏览器端 3 处文案改走 `__KTEM_t()` 查词表 |
| [libs/ktem/ktem/app.py](libs/ktem/ktem/app.py) | **功能新增** | 新增 `set_head_script()`，把词表注入 `<head>`（不能拼进 `js`，见 §3.5） |
| [libs/ktem/ktem/mcp/ui.py](libs/ktem/ktem/mcp/ui.py) | **功能新增** | MCP 工具面板的运行时标题接入翻译 |
| [libs/ktem/ktem/pages/help.py](libs/ktem/ktem/pages/help.py) | **功能新增** | Help 页按语言选择文档，支持 `*.zh.md` |
| [libs/kotaemon/kotaemon/indices/ingests/files.py](libs/kotaemon/kotaemon/indices/ingests/files.py) | **缺陷修复** | `.pdf` 默认抽取器换成 OCR 感知版本（§2.7）；`.xls` 换成 pandas 本地读取器（§2.9）；`.pptx` 换成 python-pptx 本地读取器（§5.11） |
| [libs/ktem/ktem/index/file/pipelines.py](libs/ktem/ktem/index/file/pipelines.py) | **缺陷修复** | 索引失败即回滚：不留"幽灵文件"，重试前清掉半成品块（§2.10）；重排器不可用时回退（§5.9） |
| [libs/ktem/ktem/index/file/ui.py](libs/ktem/ktem/index/file/ui.py) | **缺陷修复** | 文件列表 `loader` 列显示解析失败原因（§2.10） |
| [libs/ktem/ktem/main.py](libs/ktem/ktem/main.py) | **功能新增** | 启动时在后台调度孤儿文件自愈（§2.10） |
| [libs/kotaemon/kotaemon/loaders/\_\_init\_\_.py](libs/kotaemon/kotaemon/loaders/__init__.py) | **功能新增** | 导出 `OCRPDFReader` |
| [libs/kotaemon/kotaemon/embeddings/fastembed.py](libs/kotaemon/kotaemon/embeddings/fastembed.py) | **缺陷修复** | 补 `query_prefix` / `passage_prefix`（E5 系列必需，见 §9.4） |
| [libs/kotaemon/kotaemon/embeddings/openai.py](libs/kotaemon/kotaemon/embeddings/openai.py) | **缺陷修复** | 补 `batch_size` 分批；再补「按服务端给出的上限自适应」（§2.10，通义真上限是 10 而非 25） |
| [libs/kotaemon/kotaemon/llms/chats/openai.py](libs/kotaemon/kotaemon/llms/chats/openai.py) | **功能新增** | 记录每次调用的 usage（含流式最后一帧，§5.10） |
| [.env.example](.env.example) | 工程化 | 补充通义 key、本地向量模型、语言、OCR 等配置项 |
| [libs/kotaemon/pyproject.toml](libs/kotaemon/pyproject.toml) | 依赖 | 新增 `rapidocr-onnxruntime`、Windows 下的 `python-magic-bin`、`.xls` 所需的 `xlrd`（§2.9） |
| [libs/kotaemon/tests/test_ingestor.py](libs/kotaemon/tests/test_ingestor.py) | 测试 | `.xls` 读取器路由的回归测试（§2.9） |
| [libs/kotaemon/tests/test_table_reader.py](libs/kotaemon/tests/test_table_reader.py) | 测试 | 断言 `xlrd` 引擎在位（§2.9） |
| [flowsettings.py](flowsettings.py) | **功能集成** | DeepSeek + 本地 FastEmbed 接入；4 个语言配置项（含回答语言）；通义批大小 10、`KH_REPAIR_ORPHAN_FILES`（§2.10）、切块 512/64（§5.7）、拒答阈值 0.45（§5.8） |
| [libs/ktem/ktem/reasoning/simple.py](libs/ktem/ktem/reasoning/simple.py) | **功能新增** | 三条对话路径接入拒答闸门（§5.8）；正常/拒答两条路径都写查询 trace（§5.10） |
| [libs/ktem/pyproject.toml](libs/ktem/pyproject.toml) | 依赖 | 新增 `deep-translator` |
| [.gitignore](.gitignore) | 工程化 | 忽略运行时缓存目录 |
| [tools/eval_retrieval.py](tools/eval_retrieval.py) | **功能新增** | 分类指标、`--scope`、`--rerank`、`--fail-under-hit1`、退出码语义（§5.4） |
| [.github/workflows/tests.yaml](.github/workflows/tests.yaml) | 工程化 | 纳入 `tools/tests`；新增"新增模块覆盖率"报告步骤（A2） |

> `uv.lock` 另有约 4500 行 diff，但**版本发生变化的包为 0 个**：uv 0.11.13 把 lockfile 格式
> 从 `revision = 1` 升到 `revision = 3`，并给每条记录补了 `upload-time` 字段，详见 §3.9。

### 新增文件

| 文件 | 行数 | 说明 |
|---|---|---|
| [libs/ktem/ktem/utils/selector.py](libs/ktem/ktem/utils/selector.py) | 43 | 抽出选择器的纯逻辑，使其可脱离 Gradio 单测 |
| [libs/kotaemon/kotaemon/loaders/ocr_pdf_loader.py](libs/kotaemon/kotaemon/loaders/ocr_pdf_loader.py) | 153 | OCR 感知的 PDF 抽取器：按页判断文字层，扫描页走本地 OCR |
| [libs/kotaemon/tests/test_ocr_pdf_reader.py](libs/kotaemon/tests/test_ocr_pdf_reader.py) | 129 | 上述抽取器的测试（7 个用例，假引擎，离线） |
| [libs/ktem/ktem/assets/i18n/zh.json](libs/ktem/ktem/assets/i18n/zh.json) | 336 条 | 中文词表（生成后入库，使新 clone 开箱即中文，见 §9.7） |
| [tools/eval_retrieval.py](tools/eval_retrieval.py) | 300 | 检索评测脚本（只跑检索层，零 token 成本，见 §九） |
| [tools/reindex_corpus.py](tools/reindex_corpus.py) | 200 | 换向量模型后的索引重建工具（丢库、还原文件名、检查失败状态，见 §9.6） |
| [tools/eval/zh-points-rules.json](tools/eval/zh-points-rules.json) | 27 题 | 评测集：期望页码 + 关键事实（语料名与机构信息已脱敏） |
| [README.md](README.md) | — | 项目门面：定位、架构、亮点、指标、快速开始 |
| [libs/ktem/ktem/utils/i18n.py](libs/ktem/ktem/utils/i18n.py) | 1054 | 采集显示属性 → 调翻译库/模型 → 落盘词条缓存 → 回写 UI；含运行时翻译层（`tr` / `translate_message` / `install_hooks` / `bootstrap_js`）与源码串提取 |
| [libs/ktem/ktem_tests/test_file_selector.py](libs/ktem/ktem_tests/test_file_selector.py) | 64 | 检索范围缺陷的回归测试（10 个用例） |
| [libs/ktem/ktem/index/file/repair.py](libs/ktem/ktem/index/file/repair.py) | 246 | 孤儿文件自愈：找出「有行无向量」的文件并重新解析（§2.10） |
| [libs/ktem/ktem_tests/test_orphan_repair.py](libs/ktem/ktem_tests/test_orphan_repair.py) | 376 | 上述自愈的测试（10 个用例，含半成品判定、重试记账、失败回滚） |
| [libs/kotaemon/tests/test_embedding_batching.py](libs/kotaemon/tests/test_embedding_batching.py) | 150 | 向量批大小自适应测试（9 个用例，假 provider，离线） |
| [tools/doctor.py](tools/doctor.py) | 380 | 自检命令：索引完整性、空块、配置是否真生效、检索 smoke（§5.5） |
| [tools/tests/test_doctor.py](tools/tests/test_doctor.py) | 190 | 自检判定逻辑的测试（16 个用例） |
| [tools/tests/test_eval_retrieval.py](tools/tests/test_eval_retrieval.py) | 250 | 评测打分/分类/范围/退出码的测试（13 个用例） |
| [tools/eval/README.md](tools/eval/README.md) | — | 评测说明：口径、题目格式、换语料与加题纪律（§5.4） |
| [scripts/bootstrap_windows.ps1](scripts/bootstrap_windows.ps1) | 145 | 一键启动：Python 3.10 → uv sync → .env → 启动（§5.6） |
| [libs/kotaemon/kotaemon/abstain.py](libs/kotaemon/kotaemon/abstain.py) | 60 | 拒答闸门的纯逻辑：忽略关键词哨兵分、阈值判定（§5.8） |
| [libs/ktem/ktem_tests/test_abstain_gate.py](libs/ktem/ktem_tests/test_abstain_gate.py) | 150 | 闸门与审计日志的测试（13 个用例） |
| [tools/eval/zh-no-answer.json](tools/eval/zh-no-answer.json) | 12 题 | 无答案集：校准拒答阈值（§5.8） |
| [libs/kotaemon/kotaemon/rerankings/local_lexical.py](libs/kotaemon/kotaemon/rerankings/local_lexical.py) | 120 | 零依赖本地词法重排（中文 bigram 覆盖；只重排不丢块，保留原相似度）（§5.9） |
| [libs/kotaemon/kotaemon/rerankings/resolve.py](libs/kotaemon/kotaemon/rerankings/resolve.py) | 45 | 重排器选择：配置了但不可用（Cohere 无 key）时回退到本地（§5.9） |
| [libs/ktem/ktem_tests/test_local_reranker.py](libs/ktem/ktem_tests/test_local_reranker.py) | 190 | 词法打分/重排/回退的测试（20 个用例） |
| [libs/kotaemon/kotaemon/llms/usage.py](libs/kotaemon/kotaemon/llms/usage.py) | 70 | 进程级 LLM 用量记账（调用数/token），供 trace 取每题 delta（§5.10） |
| [libs/ktem/ktem/utils/trace.py](libs/ktem/ktem/utils/trace.py) | 110 | 每题 trace（JSONL）：召回数/最高分/拒答/延迟/token，`KH_QUERY_TRACE` 开关（§5.10） |
| [tools/trace_report.py](tools/trace_report.py) | 150 | trace 聚合报告：拒答率、P50/P95、每题 token 与调用数（§5.10） |
| [tools/tests/test_trace.py](tools/tests/test_trace.py) | 200 | 用量计数/trace 记录/聚合的测试（12 个用例） |
| [libs/kotaemon/kotaemon/loaders/pptx_loader.py](libs/kotaemon/kotaemon/loaders/pptx_loader.py) | 150 | 本地 `.pptx` 读取器：一页一条、表格转 CSV、带备注（§5.11） |
| [libs/kotaemon/tests/test_pptx_reader.py](libs/kotaemon/tests/test_pptx_reader.py) | 130 | 上述读取器的测试（6 个用例，夹具现场生成） |
| [libs/ktem/ktem_tests/test_i18n.py](libs/ktem/ktem_tests/test_i18n.py) | 567 | 本地化层测试（41 个用例，全程不联网） |
| [docs/about.zh.md](docs/about.zh.md) | 7 | Help 页「关于」中文版 |
| [docs/usage.zh.md](docs/usage.zh.md) | 56 | Help 页「使用指南」中文版 |
| `MODIFICATIONS.md` | — | 本文档 |

`.env` 为本地配置（已被 git 忽略），不计入。

---

## 二、核心改动：修复默认配置下「检索静默失效」

> 这是本项目最有价值的改动，建议作为简历和面试的主线。

### 2.1 现象

应用启动、登录、上传文档、构建索引全部正常，索引列表里也能看到文档。
但**直接提问时，模型会绕开项目文档、用自己训练时的知识作答**，且引用栏显示
`No evidence found.`。

实测对比（同一份《差旅报销制度》文档，同一个问题「一类城市的住宿费上限是多少？」）：

| | 回答内容 | 引用 |
|---|---|---|
| 修复前 | 「根据**中央和国家机关差旅费管理办法**，一类城市住宿费标准为部级 1100 元、司局级 650 元、其他 500 元」 | `No evidence found.` |
| 修复后 | 「根据**《星河科技有限公司差旅报销制度（2025 版）》第三章**，P1–P4 为 500 元、P5–P7 为 700 元、P8 及以上为 1000 元」 | `smoke-test.md`，向量检索得分 0.31，附被引用原文 |

修复前那个答案**语气专业、格式完整、数字具体，但和项目文档毫无关系**——这是 RAG 系统最危险的失败模式：
不是抛异常，而是**静默地退化成纯 LLM 调用并产生幻觉**。

### 2.2 定位过程

1. **确认不是模型问题**：把检索范围显式设成某个文件（`Search In File(s)` 模式）后，
   回答立刻变得正确且带引用 → 说明模型、向量库、索引都没问题，问题出在**检索范围解析**。
2. **缩小到选择器**：对比三种模式的行为，只有显式选择文件能召回，另两种模式召回为空。
3. **读代码定位**：
   - [ui.py:1759](libs/ktem/ktem/index/file/ui.py#L1759) `FileSelector.default()` 返回的默认模式是
     **`"disabled"`**，而该 Radio 的可选项只有 `Search All` 与 `Search In File(s)`
     —— **默认值不在选项里**，浏览器中渲染为「什么都没选中」。
   - [ui.py:1819](libs/ktem/ktem/index/file/ui.py#L1819) `get_selected_ids()` 对 `mode == "disabled"`
     直接 `return []`。
   - [pipelines.py:142](libs/ktem/ktem/index/file/pipelines.py#L142) 收到空列表后
     **直接跳过检索**：`if not doc_ids: logger.info("Skip retrieval ..."); return []`。

### 2.3 根因

**两个缺陷叠加**：

1. **默认值失效**：`default()` 返回的 `"disabled"` 不在 Radio 的 `choices` 中，UI 初始状态为未选中，
   用户不主动点选就会一直走「跳过检索」分支。
2. **状态陈旧**：`all`（全库检索）分支依赖 `gr.State` 里的 `user_id`，该 State 初始值是一个哨兵值 `-1`，
   且**只在用户手动切换模式单选按钮时**才会通过 change 事件被刷新。而 `chat_fn()` 本来就把
   权威的 `user_id` 作为参数传下来了，却没有传给选择器——导致 `all` 模式查询 `user == -1`，
   同样返回空列表。

### 2.4 修复

- **改默认值**：默认模式改为「全库检索」，使开箱即用。
- **传递权威身份**：给 `get_selected_ids()` 增加可选参数 `user_id`，优先使用会话传入的权威值，
  仅在未传入时回退到旧的 State 值（**保持向后兼容**）；并在全部 5 个调用点把已有的 `user_id` 传下去，
  覆盖 File 索引与三个 GraphRAG 索引（GraphRAG / LightRAG / NanoGraphRAG）分支。
- **抽出可测逻辑**：把模式常量、可选模式集合、默认模式与用户 id 解析抽到
  [libs/ktem/ktem/utils/selector.py](libs/ktem/ktem/utils/selector.py)。
  这样做的直接好处是：**「默认模式必须在可选集合内」这条被违反的不变量，从隐含约定变成了可断言的常量关系**，
  并且测试无需引入 Gradio 与数据库。

```python
# libs/ktem/ktem/utils/selector.py
SELECTOR_CHOICES = (SELECTOR_MODE_ALL, SELECTOR_MODE_SELECT)
DEFAULT_SELECTOR_MODE = SELECTOR_MODE_ALL      # 必须 ∈ SELECTOR_CHOICES
SELECTOR_STATE_SENTINEL = -1

def resolve_selector_user_id(session_user_id, selector_user_id):
    """优先使用会话携带的权威 user id，仅在会话没有时才回退到组件 State。"""
    if session_user_id is not None:
        return session_user_id
    return selector_user_id
```

### 2.5 验证证据

**(a) 端到端行为验证**：通过 Gradio 的 HTTP API 驱动真实 UI 事件序列
（登录 → 提交问题 → 触发推理），**刻意不触发模式单选按钮的 change 事件**，
即完全模拟「用户登录后直接提问」这一默认路径。

| 场景 | 结果 |
|---|---|
| 修复前，默认路径 | 召回为空，引用栏 `No evidence found.`，模型凭训练记忆作答 ❌ |
| 修复后，默认路径 | 召回成功，答案与文档一致，引用 `smoke-test.md`（向量得分 0.31）✅ |
| 修复后，`Search In File(s)` 模式（回归） | 仍然正常，答案「须在出差结束后 10 个工作日内提交」，带引用 ✅ |

**(b) 回归测试**：

```powershell
.\.venv\Scripts\python.exe -m pytest libs/ktem/ktem_tests/ -q
# 相关文件：test_file_selector.py（新增 10 例）+ test_conversation.py（原有 14 例）
# 结果：24 passed in 0.06s
```

### 2.6 测试落点说明（避免踩坑）

`libs/ktem/ktem_tests/` **本来就是存在的**，但：

- 它的既有约定是**零依赖纯函数测试**（直接 import `ktem.utils.*`，配 `@pytest.mark.parametrize`），
  不引入 Gradio / 数据库。因此本次把逻辑抽到 `ktem/utils/selector.py` 而不是直接测 UI 类。
- CI（[.github/workflows/unit-test.yaml:113](.github/workflows/unit-test.yaml#L113)）
  **只对 `libs/kotaemon` 执行 pytest**，`libs/ktem/ktem_tests/` 未被 CI 覆盖。
- `test_qa.py` 是上游自带、**无法收集**的用例（`from index import …` 解析不到），
  所以对整个目录执行 pytest 会直接中断；验证时按文件运行。
- 另有一坑：应用**运行时**跑测试会因 sqlite / LanceDB 被占用而长时间无输出，
  先停掉应用再跑（这不是测试本身的问题）。

### 2.7 同类缺陷二：扫描版 PDF 的正文根本没进索引

**(a) 现象**：中文提问「英语四六级能加几分」，界面回答「上下文只列出了积分细则的各大项标题…
各项目的具体评分条目并未在上下文中给出」，引用栏命中的是一张页面图片。

**(b) 定位**：直接导出索引内容（LanceDB 文档库 `docstore/index_1`），10 个块里——

| 块 | 内容 | 长度 |
|---|---|---|
| 2–5 | 各级标题（`一、思想政治表现积分（满分15分）`…） | 37–59 字符 |
| 6–9 | `Page thumbnail`（页面缩略图） | 14 字符 |
| — | **正文** | 0 字符 |

再用 PyMuPDF / pypdf 分别直读该 PDF：**整份 4 页文档只抽出 209 个字符**，且 `一`/`二` 被抽成
「康熙部首」码位（U+2F00）——这是扫描件 + 残缺文字层的典型特征：正文是图片，文字层里只有标题。

**(c) 根因**：默认 PDF 抽取器 `PDFThumbnailReader` 只读文字层，扫描件等于抽空；
它还会把每页渲染成图片块（`Page thumbnail`）塞进索引，这些块对**纯文本模型**（DeepSeek）
毫无用处，却白占 `top_k` 名额，把真正有用的文本块挤掉。

**(d) 修复**：新增 `OCRPDFReader`（[ocr_pdf_loader.py](libs/kotaemon/kotaemon/loaders/ocr_pdf_loader.py)），
**按页决策**：

- 文字层 ≥ `min_text_chars`（默认 200）→ 直接使用文字层，数字版 PDF 零额外开销、零质量损失；
- 否则把该页渲染成 200 DPI 图片交给**本地 OCR**（`rapidocr-onnxruntime`：PP-OCR 模型跑在
  已安装的 onnxruntime 上，不需要 PyTorch，模型随 wheel 自带，全程离线）；
- OCR 无结果或引擎不可用时**保留原有文字层**，绝不把页面变成空；
- 引擎为模块级单例 + 锁，多文件并发索引时不会并发进 onnx。

并把 `KH_DEFAULT_FILE_EXTRACTORS[".pdf"]` 换成它（`PDF_OCR_ENABLED=false` 可回退到原行为）。

**(e) 效果**：同一份 PDF 从 **209 字符 → 2322 字符**，4 页全部按页成块（每页 480–633 字符），
不再产生无用的缩略图块。

**(f) 验证**：重建索引后同一个问题得到

> 英语四级通过加 **4 分**；英语六级通过加 **6 分**。原文：“英语四级、六级通过分别加4分和6分。”

引用为 `[第 2 页]`，带 PDF 预览链接与原文高亮 ✅

**(g) 测试**：[test_ocr_pdf_reader.py](libs/kotaemon/tests/test_ocr_pdf_reader.py) 7 例
（假引擎，离线 3 秒跑完）：文字层足够时不 OCR、不足时 OCR、OCR 空结果时保留文字层、
无引擎时降级、空页跳过、元数据满足引用面板。

**(h) 代价与取舍**：OCR 约 **8 秒/页**（200 DPI）。只有缺文字层的页面会触发，
数字版 PDF 完全不受影响；超长扫描件（上百页）建索引会比较慢，可调 `PDF_OCR_DPI` 降速。

### 2.8 同类缺陷三：`.docx` 上传成功但索引从未写入

**(a) 现象**：用户上传一份 `奖助学金评定通知.docx`，文件列表里**有这一行**，
但 `token` 与 `loader` 两列都是 `-`；提问相关内容时回答「未在上下文给出」、引用栏
`No evidence found.`。用户以为"上传了却没读到"。

**(b) 定位**：查 `index__1__source.note` —— PDF 是 `{"tokens": 2562, "loader": "OCRPDFReader"}`，
而这个 docx 是 **`{}`**，且 `index__1__index` 里 **0 个文档块**。
也就是说 Source 行建了，但索引阶段失败了，而且**失败信息没有留在 UI 上**。

再用不同读取器直接读同一份文件：

| 读取器 | 结果 |
|---|---|
| `UnstructuredReader`（默认） | ❌ `failed to find libmagic` → 补 `python-magic-bin` 后仍 `HTTP Error 403`（其内部联网取资源） |
| `DocxReader`（python-docx，纯本地） | ✅ 2099 字符 + 3 个表格块 |

**(c) 根因**：`.docx` 默认走 `unstructured`，它依赖系统库 `libmagic`，且在本机会联网获取
自身资源并被拒；异常在 `IndexDocumentPipeline.stream` 里被吞成一条 `status: failed` 的
流式事件 —— 上传界面一闪而过，用户只看到"文件在列表里"，于是表现为"上传了但没有"。

**(d) 修复**：`KH_DEFAULT_FILE_EXTRACTORS[".docx"]` 换成项目自带的本地 `DocxReader`
（python-docx，无系统依赖、不联网，段落 + 表格分别成块）。`.doc`（老二进制格式）仍保留
`unstructured`，因为 python-docx 不支持它。

**(e) 验证**：重建后该文件 `note` 变为 `{"tokens": 2429, "loader": "DocxReader"}`、
**4 个文档块**；用真实检索管线提问「奖助学金有什么申请要求」，
前 4 条命中全部来自该 docx（相似度 0.742 / 0.715 / 0.668 / 0.513），内容含评定范围、
评定要求、截止日期 ✅

> 本节示例中的文件名与机构信息已做脱敏处理，指标与行为未变。

**(f) 附带修 UX**：即使索引正常，若检索范围是「在文件中搜索」却没勾选文件，检索仍会静默为空。
现在提问时若**没有任何可检索文件**，会直接弹提示说明原因（未上传/未索引完成，或未勾选文件），
而不是让用户对着 `No evidence found.` 猜。

> 影响范围提示：`.pptx`、`.doc` 仍走 `unstructured`，在同样的环境里可能遇到相同问题；
> 需要时按同样方式换成本地读取器（`DocxReader`/`PandasExcelReader` 等已在仓库内）。
> `.xls` 已按 §2.9 处理完毕。

---

### 2.9 同类缺陷四：`.xls`（老版 Excel）上传直接失败，索引 0 块

**(a) 现象**：上传 `中央机关…考试录用公务员招考简章.xls`（9.6 MB）后，文件列表里**有这一行**，
但 `loader` 与 `tokens` 两列都是 `-`；在对话页勾选该文件问「帮我看一下哪里有某市的岗位」，
回答是"没有联网能力"之类，引用栏 `No evidence found.`。

**(b) 定位**：`index__1__source.note` 为 **`{}`**（对比同批的 `.docx` 是
`{"tokens": 2429, "loader": "DocxReader"}`），`index__1__index` 里该 source **0 个文档块**；
对话记录里 `retrieval_messages` 就是 `No evidence found.`。再用两种读取器直接读同一份文件：

| 读取器 | 结果 |
|---|---|
| `unstructured`（原默认） | ❌ `ImportError: Missing optional dependency 'xlrd'` —— 它的 `partition` 对 `.xls` 也走 pandas |
| `PandasExcelReader` | ❌ 同一异常（`pd.read_excel` 同样需要 `xlrd`） |

**(c) 根因**：两层叠加。
1. 仓库只声明了 `openpyxl`（它只认 `.xlsx`），**没有任何地方声明 `xlrd`**，所以 `.xls` 无论走哪条路都读不出来；
2. 即使装上 `xlrd`，`.xls` 默认还挂在 `unstructured` 上，而它在 Windows 上还要 LibreOffice 做格式转换（本机没有）。

异常被 `IndexDocumentPipeline.stream` 吞成一条 `status: failed` 的流式事件，上传框一闪而过。

**(d) 修复**：
1. [libs/kotaemon/pyproject.toml](libs/kotaemon/pyproject.toml) 增加 `xlrd>=2.0.1,<3`（并同步 `uv.lock`）；
2. [libs/kotaemon/kotaemon/indices/ingests/files.py](libs/kotaemon/kotaemon/indices/ingests/files.py) 把
   `KH_DEFAULT_FILE_EXTRACTORS[".xls"]` 由 `unstructured` 换成 `PandasExcelReader()`，与 `.xlsx`
   共用同一条**纯本地**路径（无系统依赖、不联网、不需要 LibreOffice）。

**(e) 验证**：`PandasExcelReader` 读该 9.6 MB 文件 **1.9 s**、出 1 篇文档、**6,858,508 字符**，
首行即表头「部门代码 部门名称 用人司局 机构性质 …」；新增回归测试
`test_xls_is_read_locally_by_pandas`（路由不落回 unstructured）与
`test_xls_engine_available`（`xlrd` 引擎在位），连同 `test_ingestor.py` / `test_table_reader.py`
共 **5 passed, 1 skipped**；CI 那套测试子集 **62 passed**（其余 26 个是沙箱里 `tmp_path` 建不出来的环境问题，与本次改动无关）。

**(f) 已经失败过的文件不会自己变好**：Source 行还在库里、块还是 0 个，必须重新解析一次 ——
现在这一步由 §2.10 的启动自愈自动完成（重启应用即可）；也可以手动：应用**停止**时跑
`python tools/reindex_corpus.py --match 中央机关`，或在「上传并索引」勾选 `Force reindex file` 重传。

> 影响范围提示：`.doc`、`.pptx` 仍走 `unstructured`；`.csv` 虽出现在可上传类型里，
> 但没有专门的抽取器（会落到 `unstructured`），需要的话同样换成 pandas 读取器。

---

### 2.10 根治：解析/索引失败不再变成「幽灵文件」，并在启动时自动修好历史遗留

§2.7、§2.8、§2.9 是**同一形状的三次复现**：解析或建索引抛异常 → 异常被当成一条流式事件闪过 →
`Source` 行留在库里、块（尤其向量）一个没有。用户侧固定三步：文件列表里有这一行 → 提问时勾选它 →
`No evidence found.`。每次都得靠人工发现"这个文件其实没进索引"，再手工重建。

**(a) 三处代码改动**

1. **失败即回滚**（[pipelines.py](libs/ktem/ktem/index/file/pipelines.py) `IndexPipeline._handle_failed_indexing`）：
   - 上传失败：这次尝试自己新建的 `Source` 行连同存储副本一起删掉，用户看到上传框的 ❌ + 原因，**重传即可**，
     不会再撞 "already indexed"；
   - 自愈重试失败：保留用户的 `Source` 行，但把**已写入的半成品块删掉**——索引先写文档库、后写向量库，
     失败时真的会留下「10237 个文档块 / 0 个向量块」这种看起来已索引、实际检索不到的状态。
   - `delete_file` 现在同时删除磁盘上的存储副本（原来只删库，文件永久占盘）。

2. **启动自愈**（新增 [repair.py](libs/ktem/ktem/index/file/repair.py)，由
   [main.py](libs/ktem/ktem/main.py) `App.repair_orphan_files` 在启动时起后台线程）：
   扫描「有 `Source` 行但**没有向量块**」的文件，用存储副本 + 原文件名重新解析并索引。
   修好读取器/批大小后，老文件**下次启动自动补进索引**，不需要人工 Force reindex。
   每个文件最多重试 3 次（`note["repair_attempts"]`），避免坏文件每次开机都重算；开关 `KH_REPAIR_ORPHAN_FILES`（默认开）。

3. **失败可见**（[ui.py](libs/ktem/ktem/index/file/ui.py) `describe_loader`）：文件列表 `loader` 列对失败的
   文件显示 `⚠ <原因>`（如 `⚠ Missing optional dependency 'xlrd'`），一眼区分"没解析成功"和"已索引"。

**(b) 同时修掉的一个更硬的上游缺陷：向量批大小**（[openai.py](libs/kotaemon/kotaemon/embeddings/openai.py)）
`batch_size` 配的是 25（按文档写的"通义单次上限"），但 `text-embedding-v3` 实测**上限是 10**，接口直接 400。
后果：**任何超过 10 块的文件都永远建不进索引**（3~4 块的小文件正好绕过）。现在两层修复：
配置里改成 10；并且客户端在服务端报「batch size is invalid ... not larger than 10」时会**自动采用服务端报出的上限**
（无数字则折半），并把该上限记在实例上，一次踩坑、整轮不再复发。回归测试 `test_embedding_batching.py`（9 例）。

**(c) 验证**（本机实测）
- 修复前该 `.xls`：`docs=10237, vecs=0, note={}` —— 文件在列表里、检索返回 0 条；
- 修复后由启动自愈自动重解析（未手工重建）：`docs=10237, vecs=10237, note={"tokens": 6983734, "loader": "PandasExcelReader"}`，
  索引耗时 593 s（通义每次 10 条，约 1000 次请求）；
- **检索实测**：勾选该文件问「哪里有某市的岗位」→ **10/10 命中**某市岗位行，
  Top1 = 0.567「某市税务部门 … 湖南省某市北塔区 …」（改前是 `No evidence found.`）；
- 回归测试：`test_orphan_repair.py` 10 例（孤儿按向量判定、半成品也算孤儿、原名还原、失败保留上传、
  重试计数落在**重建后的新行**上、重试上限、按 owner 解析、loader 列、失败回滚/清块的决策），
  `test_embedding_batching.py` 9 例（分批、按服务端上限重试、折半退化、无关错误不重试、顺序还原）。

**(d) 为什么不是"手动重建一次"**：这三个缺陷的共同点是**失败被静默吞掉**。只补数据不改机制，
下次换个格式/换个模型上限还会重演；改动后失败会回滚、会记原因、会在启动时自愈。


---

## 三、界面汉化（引入翻译库，译文不入代码）

### 3.1 为什么必须自己补一层

上游使用的 Gradio **4.39 不具备任何 i18n 机制**（`gr.I18n` 到 5.x 才引入），界面文案全部硬编码
散落在 20 多个 UI 文件里。而直接把中文译文写进源码又会带来两个问题：
一是译文与代码耦合、改动要动业务文件；二是维护者无法单独更新词条。

因此本 fork 的做法是：**译文一律不写进源码**，而是由翻译库联网生成、落盘成词条缓存，
启动时只读缓存。

### 3.2 数据流

```
                    ┌─ collect_display_strings()  构建后的组件树：只采集「会被渲染成文字」的属性
待翻译字符串集合 ◀──┤
                    └─ collect_source_strings()   AST 扫源码：tr() / gr.Info 等运行时串 + JS 里的 __KTEM_t()
   │  翻译库/模型批量翻译（仅缺失项）+ 结构校验 + 冲突校验
   ▼
ktem_app_data/i18n/zh.json               词条缓存（JSON，336 条，不入库）
   │
   ├─ localize_blocks()        构建期：回写组件显示属性
   ├─ tr() / translate_message()  运行时：引用块标签、toast 消息（含 f-string 模板回填）
   └─ bootstrap_js()           浏览器端：注入 window.__KTEM_t，供 main.js 查词表
   ▼
全中文界面                                 启动只读缓存，秒级完成、之后无需联网
```

新增依赖：`deep-translator>=1.11.4`（写入 [libs/ktem/pyproject.toml](libs/ktem/pyproject.toml)）。
`llm` 后端不需要新依赖，直接复用项目已配置的 OpenAI 兼容客户端。

### 3.3 安全模型：只翻「显示属性」，绝不碰「值」

译文来源换成了外部服务，但**改坏功能的风险点不变**，所以沿用同一套约束
（见 [libs/ktem/ktem/utils/i18n.py](libs/ktem/ktem/utils/i18n.py)）：

- 只改写按组件类型白名单列出的显示属性：
  `label` / `info` / `placeholder` / `Button.value` / `Markdown.value` / `HTML.value` /
  `Dataframe.headers` / `choices`。
- **绝不改写输入组件的 `value`**：`Textbox.value`（提示词模板）、`Code.value`（配置内容）、
  `State` 等是真实数据，动了就坏功能。因此 `collect_display_strings()` 也不会把它们送去翻译。
- 只翻译**不含中日韩字符**、且长度 ≤ 500 字符的字符串；长文档走 §3.4 的文件方案。

**关键设计**：Gradio 一律把 `choices` 规范化成 `(显示标签, 实际值)` 二元组，
因此翻译选项时只改标签、值原样保留；`choices=["all","text"]` 这类「裸字符串」
（字符串既是标签也是值）会被展开为 `("全部", "all")`，保证值仍是原字符串。

```python
# 翻译前  [("Search All", "all"), ("Search In File(s)", "select")]
# 翻译后  [("检索全部",   "all"), ("指定文件",        "select")]   ← 值没变
```

### 3.4 Help 页单独处理

Help 页的长文档不是组件文案，而是从 `docs/about.md` / `docs/usage.md` 读取的文件内容，
机器翻译长文效果差且易超长被拒。因此改为**按语言选文件**：优先读 `about.<lang>.md`，
不存在则回退 `about.md`（再回退到远程仓库），并补充了
[docs/about.zh.md](docs/about.zh.md) 与 [docs/usage.zh.md](docs/usage.zh.md)。

### 3.5 运行时字符串：三条绕开组件树的通道

3.2 的遍历只覆盖「构建完成时**已经存在**的组件属性」。第一版做完后页面刷新仍有英文：
页脚 `version:`、右栏 `Relevance score` / `Image from` / `[Page 1]` / `[Preview]`、
快速上传提示 `Please wait for the indexing process…`。根因是这些串在 `app.make()`
**之后**才产生，遍历时根本不存在，也从未进入词表。

| 通道 | 典型串 | 为什么遍历看不到 | 处理 |
|---|---|---|---|
| Python 运行时拼装 | `[Page {}]`、`[score: {}]`、`{} from`、`Relevance score`、`Vectorstore score:`、`LLM relevant score:`、`Reranking score:`、`(full-text search)`、`[Preview]` | 在 [render.py](libs/ktem/ktem/utils/render.py) 渲染引用块时才拼接 | `tr()` 包裹 |
| 事件回调里的字面量 | `Please wait for the indexing process…`、`Indexing completed.`、`### Add new group` | 写在 `lambda: gr.update(value=…)` 里，点击后才执行 | `tr()` 包裹 |
| 浏览器端拼装 | `version: 0.12.0`、`Browse conversation`、`Explain ` | 由 [main.js](libs/ktem/ktem/assets/js/main.js) 在浏览器里生成，Python 侧完全不可见 | 注入 `window.__KTEM_t()` 查词表 |

三条通道共用**同一份词表**（[i18n.py](libs/ktem/ktem/utils/i18n.py)）：

- `tr(text)` —— 运行时精确查表，查不到原样返回，所以包一层永远不会坏事。
- `translate_message(text)` —— 额外支持 **f-string 模板回填**。约 50 条 toast 形如
  `f'Index "{name}" created successfully'`，运行时已经是 `Index "docs" created successfully`，
  无法精确命中。因此采集阶段把插值位置记为 `{}`（`Index "{}" created successfully`），
  译文要求占位符数量一致，运行时用正则匹配出插值再填回去。
- `install_hooks()` —— 只改 **3 个入口**（`gr.Info` / `gr.Warning` / `gr.Error.__init__`）
  就覆盖全项目约 50 条弹窗提示，不必逐个改调用点。`Error` 是类且被 `except gr.Error` 使用，
  所以改的是 `__init__`，替换类本身会让 `except` 子句直接报错。
- `bootstrap_js()` —— 把词表序列化成 `window.__KTEM_I18N`，并定义
  `__KTEM_t(s) = __KTEM_I18N[s] ?? s`；英文模式下同样定义（退化为恒等函数），
  否则 `main.js` 调用时会报未定义。注入位置是 **`<head>` 里的 `<script>`**，原因见下面的踩坑。

> **踩坑（一度把整个前端搞挂）**：最初把这段词表**拼在 `gr.Blocks(js=...)` 前面**，结果页面只剩
> 一个「欢迎」标题、登录框都不出现，完全进不去。根因在 Gradio 的实现：它把 `config.js`
> 当成**一个函数表达式**，包装成 ``let result = await (${js})();``。上游 `main.js` 正好是
> `function run(){…}`，合法；一旦在前面拼上 `window.__KTEM_I18N = …; window.__KTEM_t = …;`，
> 就成了括号里的语句序列 → **编译期 `SyntaxError: Unexpected token ';'`**，整段脚本一行都没执行：
> `run()` 没跑 → `getStorage()` 没挂到 `globalThis` → 登录页 load 事件的 `fetch_creds` 跟着抛错 →
> `toggle_login_visibility` 不执行 → 登录框永远停在 `visible=False`。
> 更隐蔽的是**服务端完全正常**：`/config` 仍返回 457 个组件、`/chat_fn` 也能正常出答案，
> 只跑接口测试根本发现不了。
> 修法：改为注入 `<head>`（纯 HTML，不经过这层包装）；`bootstrap_js()` 里把 `</` 转义成 `<\/`，
> 防止译文里的 `</script>` 提前闭合标签；并补了一条回归测试。
> 教训：**改了前端注入点必须在真实浏览器里看一次**——这次是用 Chrome DevTools Protocol
> 抓 `Runtime.exceptionThrown` 才定位到的。

**这些串怎么进词表**：它们不在组件树里，`collect_display_strings()` 采不到，于是加了
`collect_source_strings()` —— 用 `ast` 扫描源码，收集 `tr(...)` 与 `gr.Info/Warning/Error(...)`
的字符串字面量（f-string 转成模板），再用正则收集 JS 里的 `__KTEM_t("...")`。
相当于把 gettext 的 `xgettext` 提取步骤实现了一遍，**以后新增调用点会自动进入词表，不用手工登记**。

> 设计取舍：为什么不直接在浏览器里遍历 DOM 替换文本？因为那会把**模型回答和文件名一起翻掉**。
> 只翻「我们在源码里明确标记过的串」才能保证用户数据和模型输出不被误伤。

### 3.6 让回答也用中文（不止界面）

只把界面汉化还不够：中文提问、文档也是中文，模型却仍用英文回答。原因是答案语言由
QA 提示词末尾那句 `Give answer in {lang}.` 决定，而 `{lang}` 来自设置项 `reasoning.lang`，
其默认值是写死的 `"en"`。

改动只有两处（[flowsettings.py](flowsettings.py)）：

```python
KH_ANSWER_LANGUAGE = config(
    "KH_ANSWER_LANGUAGE",
    default=KH_UI_LANGUAGE if KH_UI_LANGUAGE in SUPPORTED_LANGUAGE_MAP else "en",
)
# SETTINGS_REASONING["lang"]["value"] = KH_ANSWER_LANGUAGE   # 原为 "en"
```

这样「界面语言 = 回答语言」，也仍然可以在聊天设置的下拉框里单独改（对话标题生成、
追问建议走的都是同一个 `lang`，一并变中文）。要英文回答时设 `KH_ANSWER_LANGUAGE=en`。

> 注意：这是**用提示词约束模型输出中文**，不是把英文回答再机器翻译一遍。
> 后者会破坏引用标记、二次消耗 token、还可能改写文档中的原文数值。

### 3.7 配置与使用

新增配置项（均可由环境变量 / `.env` 覆盖）：

| 配置项 | 默认 | 作用 |
|---|---|---|
| `KH_UI_LANGUAGE` | `zh` | 界面语言；设为 `en` 即还原上游英文界面 |
| `KH_UI_TRANSLATOR` | `llm` | 翻译后端：`llm`（复用已配置的对话模型）/ `mymemory` / `google` / `libre` |
| `KH_UI_TRANSLATE_MISSING` | `false` | 是否在启动时翻译缺失词条（默认关闭，保证启动快） |
| `KH_ANSWER_LANGUAGE` | 跟随 `KH_UI_LANGUAGE` | 模型**回答**语言；设 `en` 可让界面中文但回答英文 |

> `deep-translator` 是默认库后端；`llm` 后端走项目已配置的对话模型（不需要额外凭据）。
> 两者都只在**构建词条缓存时**使用，运行时只读缓存。

构建/更新词条缓存（一次即可）：

```powershell
.\.venv\Scripts\python.exe -m ktem.utils.i18n build --language zh --backend llm
.\.venv\Scripts\python.exe -m ktem.utils.i18n stats --language zh
```

### 3.8 验证证据与实测数据

**(a) 后端实测**（这是选型依据，不是推断）：

| 后端 | 结果 |
|---|---|
| `google` | **不可用**。即使按 0.35 秒节流 + 3 次退避重试，仍持续返回 `TooManyRequests`（HTTP 429） |
| `mymemory` | **可用但不达标**。约 2.5 秒/条、250 条约需 10 分钟；偶发繁体用词；**且会破坏 Markdown 结构**：`## Conversations` 的 `##` 被丢弃、`**Simple QA**` 退化成 `* *简单QA * *`、偶发返回 `<g id="1">…</g>` 标记 |
| `llm` | **采用**。复用已配置的 DeepSeek，Markdown 结构完整保留（`## Conversations` → `## 对话`）、术语一致、并发 4 路后整批约 2–4 分钟 |
| `libre` | 公共实例需 API key，未采用 |

因为翻译是一次性成本，慢可以接受；但**破坏 Markdown 会直接显示成字面量 `*` / `#`**，
所以引入了结构校验：译文若丢失标题标记、`**` 配对或列表符号，就**丢弃译文并保留英文原文**
（见 `clean_translation()`），保证任何一种后端都不会把界面翻坏。

**(b) 覆盖率与安全性核对**（比对本地化后的 `/config`）：

- 界面显示文案中的英文条目由 264 条降至 **18 条**，且均为刻意保留：品牌名 `Kotaemon`、
  专有名词 `Google` / `Wikipedia` / `LLM`、学术方法名 `ReAct` / `ReWOO`、
  模型供应方名 `openai` / `deepseek` / `claude`，两个被模型判定为标识符的表头
  （`tokens` / `date_created`），以及 2 段纯 HTML 片段（`<br/>`、`<div id='pdf-modal'></div>`）。
  词条缓存共 **336 条**，启动日志：`UI language 'zh': 296 labels localized, 336 catalog entries, 18 missing`。
- **值完整性逐条核对通过**：`all` / `simple` / `en` / `off` / `hybrid` 等后端用于匹配的值
  全部未变，`choices` 的第二个元素原样保留。
- **语言下拉无重复**：`英语 / 日语 / 越南语 / 西班牙语 / 法语 / 德语 / 中文 / 俄语 …`
  —— 这里踩过一个真实缺陷，见 §3.8(d)。

**(c) 两道自动校验**（缺陷驱动，已写成单元测试）：

| 校验 | 解决的问题 |
|---|---|
| `clean_translation()` | 译文丢失标题 `#`、`**` 配对或列表符号、或夹带 `<g>` 标记时**丢弃译文保留英文**，避免界面出现字面量 `*` / `#` |
| `drop_conflicting_translations()` | 两个不同源串翻成同一结果时判定为歧义并丢弃（按大小写 / 单复数归一化，避免误伤 `Admin`/`admin`、`Vendors`/`vendor`） |

**(d) 一个真实踩坑**：逐条翻译时，语言名会被"目标语言"污染 —— `English` 被翻成了「中文」，
和 `Chinese` 撞车，下拉框里出现两个"中文"。改为**批量翻译**（一次送一组，模型能看到同类项上下文）
后修复；冲突校验作为兜底保留。

**(e) 功能回归（含回答语言）**：汉化后经 `/chat_fn` 接口实测端到端问答：

- **回答是中文且有据可依**：`思想政治表现积分 15 分 / 学业积分 15 分 / 服务积分 40 分`，
  并注明「见第 1 页」「见第 2 页」，与文档原文一致 ✅
- **引用栏同步为中文**：`图像 来自 [第 1 页] …`、`[得分：0.0]`、`相关性分数`、
  `向量存储得分：`、`LLM 相关度评分：`、`重排序分数：`、`[预览]` ✅

> 验证时踩到的一个坑：**未登录的 API 会话** `user_id` 为 `None`，`get_selected_ids()`
> 直接返回空列表，于是检索结果为空、返回 `No evidence found.`，答案退化成模型自由发挥
> 甚至会编出错误的分数。这是未登录会话的既定行为（私人集合按用户隔离），
> **不是本次改动引入的回归**；用 `select` 模式显式传入文件 id 即可复现检索。

**(f) 运行时层验证**：

- 服务端首页 HTML 中确认注入了 `window.__KTEM_I18N` 与 `window.__KTEM_t` ✅
- `render.py` 实际输出：`<i>图像 来自 [第 1 页] paper.pdf</i> [得分：0.0]` ✅
- toast 通道由单元测试覆盖：注入探针后确认 `gr.Info("Indexing completed.")`
  实际送出的是「索引完成。」，`gr.Warning(f"Failed to create LLM 'x': {e}")` 送出
  「创建 LLM 'x' 失败：boom」✅

**(g) 浏览器端验证**（headless Chrome + DevTools Protocol，因为接口测试覆盖不到前端）：

- 控制台无 `SyntaxError` / `Uncaught`（除一条与本改动无关的 skypack `pdfjs-viewer-element`
  CDN 构建失败，属上游外部依赖问题）；
- `typeof window.__KTEM_t` 与 `typeof window.getStorage` 均为 `function`；
- 页脚版本节点实际渲染为「版本： 0.12.0」，`.header-bar` 已挂上；
- 登录表单（用户名 / 密码 / 登录）正常出现，`admin/admin` 可登录；
  登录后顶部为 聊天 / 文件集合 / 资源 / 设置 / 帮助，左栏与输入框提示均为中文 ✅
- 截图核对：登录页与登录后首页均无英文残留（`sr-only` 的无障碍标签除外）。

**(h) 单元测试**：[test_i18n.py](libs/ktem/ktem_tests/test_i18n.py) 41 个用例
+ [test_file_selector.py](libs/ktem/ktem_tests/test_file_selector.py) 10 个
+ `test_conversation.py` 14 个 + `test_mcp_manager.py` 13 个 = **78 passed**，全程不联网。
覆盖的不变量包括：「只采集显示属性、不采集数据」「选项值不被改写」「输入组件的数据不被改写」
「词条缓存读写」「批量后端只按组调用」「单条失败不影响整体」「译文结构损坏被拒绝」
「占位符丢失被拒绝」「f-string 模板能回填」「查不到时原样返回」「英文模式下钩子不生效」
「注入脚本不会提前闭合 `<script>`」。

### 3.9 已知限制

- **`uv.lock` 有约 9000 行 diff**，原因是 uv 0.11.13 把 lockfile 格式从 `revision = 1`
  升到 `revision = 3` 并给每条记录补了 `upload-time` 字段。**实测版本发生变化的包为 0 个**，
  仅新增 `deep-translator`。
- **运行时串需要显式标记**：新写的代码若忘了用 `tr()` 包裹，仍会漏翻 —— `ast` 只能采集到
  被标记的串。这是 gettext 体系的通病，靠 review 兜住，不是自动全覆盖。
- **f-string 模板回填是保守的**：译文占位符数量与原文不一致时，宁可退回英文，也不显示坏串。
- **词条缓存在 `ktem_app_data/`（已被 git 忽略）**：换机器或新 clone 首次启动仍是英文，
  需跑一次 `build` 命令（要联网 + 配置好的模型）才会变中文。若要开箱即中文，
  可把生成的 `zh.json` 提交进仓库作为默认词表、运行时优先用用户目录的缓存 —— 尚未这样做。
- 机器翻译无术语表约束，个别词条（如 `Citation style` → `引文`）可能需要手工润色；
  可修改 `ktem_app_data/i18n/zh.json` 后重启生效，无需改代码。

---

## 四、模型接入改造：DeepSeek 对话 + 本地 FastEmbed 向量

### 4.1 需求

- 对话模型：**DeepSeek API**（OpenAI 兼容接口）
- 向量模型：**本地 FastEmbed**（不调用外部 embedding API，零调用成本、数据不出网）

### 4.2 为什么不能只改 `.env`，必须改代码

上游 `flowsettings.py` 的默认项是按环境变量推导的：

- 只要设置了 `OPENAI_API_KEY`，就会同时把 `KH_EMBEDDINGS["openai"]` 设为默认，指向
  `text-embedding-3-large`。而 DeepSeek **不提供 embedding 接口**，建索引会直接失败。
- 本地 FastEmbed 条目（`fast_embed`）只在设置了 `LOCAL_MODEL` 时才创建，且 `default=False`。

因此必须修改 [flowsettings.py](flowsettings.py)：

1. 新增 `KH_LLMS["deepseek"]`，从 `DEEPSEEK_API_KEY` / `DEEPSEEK_API_BASE` / `DEEPSEEK_CHAT_MODEL`
   读取配置，`default=True`。
2. 新增 `KH_EMBEDDINGS["fast_embed"]`，模型名从 `LOCAL_EMBEDDING_MODEL` 读取，`default=True`。
3. 在文件末尾**显式压平所有 `default` 标记**，保证本地这套是唯一默认，不受 env 状态推导干扰：

```python
for _name, _cfg in KH_LLMS.items():
    _cfg["default"] = _name == "deepseek"
for _name, _cfg in KH_EMBEDDINGS.items():
    _cfg["default"] = _name == "fast_embed"
```

> **机制提醒**：模型池只在**首次启动、对应数据库表为空**时从 `flowsettings.py` 播种。
> 改完该文件若要生效，需删除 `ktem_app_data/user_data/sql.db` 后重启，或在 UI 的 Resources 页修改。

### 4.3 踩坑：FastEmbed 的中文模型在本机不可用

上游锁定的 FastEmbed `0.4.2` 中，各模型的下载源不同：

| 模型 | 下载源 | 实测 |
|---|---|---|
| `BAAI/bge-small-zh-v1.5`（中文） | 仅 `storage.googleapis.com` | **HTTP 403，不可用** |
| `BAAI/bge-small-en-v1.5`（英文） | HuggingFace | 可用 |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`（多语言，384 维） | HuggingFace | 可用（初版采用，后按评测换掉） |
| `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`（多语言，768 维） | HuggingFace | **可用，最终采用**（见 §9.4） |

初版选了 `paraphrase-multilingual-MiniLM-L12-v2`：约 235MB，覆盖约 50 种语言（含中文），
且走 HuggingFace 可正常下载。**后来建了检索评测（§九），发现它偏弱**——Hit@1 只有 36.7%——
于是按同一套评测在三个候选里重新选型，最终换成 `mpnet-base-v2`（Hit@1 60.0%，30 题口径）。

**本地向量模型实测**（不依赖任何 API，MiniLM 初版）：

```
cos(中文1, 中文2) = 0.6606
cos(中文1, 英文)  = 0.4621     # 中文语义相似度显著更高，模型工作正常
维度 = 384
```

---

## 五、工程化与其他改动

### 5.1 `.gitignore`（+7 行）

应用运行时会往仓库根目录写缓存目录，实测后补入忽略列表：

| 目录 | 来源 | 体积 |
|---|---|---|
| `fastembed_cache/` | FastEmbed 早期版本把模型缓存写在当前工作目录 | 约 240 MB（已改到应用数据目录，见下） |
| `data-gym-cache/` | tiktoken 的 BPE 缓存 | 约 1.7 MB |
| `flow_tmp/` | theflow（Gradio 状态库）的磁盘缓存 | — |

> **向量模型缓存位置**：FastEmbed 默认把 ONNX 模型放在 `tempfile.gettempdir()`，
> 而临时目录会随 `TMP` 变化、也可能被清理工具清空 —— 换一次模型约 1–2 GB，重下代价很高。
> 因此 `flowsettings.py` 里用 `FASTEMBED_CACHE_PATH` 把它固定到
> `ktem_app_data/fastembed_cache`（可用环境变量覆盖），确保位置稳定且不污染仓库。

> 顺带发现：Gradio 在 `libs/` 下自动生成的组件存根 `*.pyi` 已被上游 `.gitignore` 的
> `*.py[coid]` 规则覆盖，无需额外处理。

### 5.2 依赖安装：`llama-cpp-python` 无 Windows 轮子

`llama-cpp-python==0.2.7`（上游 `adv` 可选依赖）在 PyPI 上**只发布了源码包，没有任何 Windows wheel**，
本地无 C++ 工具链时 `uv sync` 会编译失败。因为本项目使用 DeepSeek + FastEmbed，
完全不涉及本地 GGUF 推理，故安装时排除：

```powershell
uv sync --python 3.10 --no-install-package llama-cpp-python
```

排除是安全的：该库在代码中全部为惰性导入（`TYPE_CHECKING` 或 `Param.auto()` 内部），
仅在选择 LlamaCpp 模型时才会被真正加载。

### 5.3 PDF.js 内置阅读器

按上游 README 下载 `pdfjs-4.0.379-dist.zip` 解压到 `libs/ktem/ktem/assets/prebuilt/`，
用于问答结果的 PDF 原文高亮预览。该目录被 `libs/ktem/.gitignore` 忽略。

### 5.4 评测工具升级（`tools/eval_retrieval.py`）

原来的评测只能给出一个总数字，且退出码是 `return 0 if hit_at_1 == 1.0 else 1`——
基线就在 60% 上下，等于永远"失败"，无法进 CI。这次补齐四项：

| 能力 | 用法 | 为什么 |
|---|---|---|
| 分类指标 | 题目加 `category`（T1 单跳 / T2 数值 / T3 多跳 / T4 无答案） | 一个总数字会掩盖"某一类变好、另一类变坏" |
| 范围限定 | `--scope "文件名"` | 等价界面上的「在文件中搜索」，让"某份语料多好"可复现 |
| 重排 A/B | `--rerank on` / `--rerank off` | 把重排器钉成开/关，其余条件不变（B2 的尺子） |
| 门槛与退出码 | `--fail-under-hit1 0.55`；不设阈值时完成即 0，无语料为 2 | 能进 CI，且不再把"没到 100%"判为失败 |

配套：`tools/eval/README.md`（指标口径、题目格式、如何换语料/加题、当前基线与天花板效应说明）；
`tools/tests/test_eval_retrieval.py` 13 例（匹配、名次、按类别分组、退出码、范围选择、重排开关），
全部离线、假 retriever，不需要应用与网络。

**顺带测到的一个问题**：把 10 MB / 10237 块的表格放进同一索引后，同一套 27 题在四块语料上的
指标从 **Hit@1 55.6% / facts 100%** 掉到 **33.3% / 48.1%**——召回名额被大文件占满。
这既是"不能只看总指标"的证据，也是一条新的待办（按文件配额 / 多样化重排）。

### 5.5 `doctor` 自检命令（`tools/doctor.py`）

这个项目已经出现过四次"配置写了但功能静默失效"（§2.7–§2.10），把这类状态做成一条命令：

```powershell
.\.venv\Scripts\python.exe tools\doctor.py                          # 人读表格
.\.venv\Scripts\python.exe tools\doctor.py --json x.json --strict   # CI 用
```

检查项：每个文件的 `document` / `vector` 块数与 `note`（**0 向量块 = 列表里有但检索不到**）、
空文本块比例、向量 provider 与模型、重排器有没有 key、`chunk_size`、`PDF_OCR_ENABLED`、
启动自愈开关、词表条数，以及 3 道固定题的召回 smoke。任一 FAIL 返回 1，`--strict` 让 WARN 也返回 1。

判断逻辑（哪条算 FAIL / WARN、退出码）抽成纯函数，`tools/tests/test_doctor.py` 16 例覆盖。
首次实测：12 项检查、0 FAIL / 2 WARN（重排无 key、`chunk_size=0`），与 README「已知限制」一致。

### 5.6 一键启动脚本（`scripts/bootstrap_windows.ps1`）

`uv sync` 在 Windows 上必须带 `--no-install-package llama-cpp-python`（无轮子），这是新手第一个坑；
脚本把 Python 3.10 检查、依赖同步、`.env` 生成（**已存在则绝不覆盖**）、临时目录重定向与启动串起来。
纯 ASCII 书写（PowerShell 5.1 读无 BOM 脚本按 GBK 解析，中文会导致语法错误），`-NoStart` 可只准备环境。

**双击入口**：`.ps1` 双击不会执行（Explorer 用记事本打开，或被执行策略拦下），所以根目录另放
`start.bat`：`cd /d "%~dp0"` → `powershell -ExecutionPolicy Bypass -File scripts\bootstrap_windows.ps1 %*`
→ 失败时 `pause` 留窗并打印日志路径。它只做转发，参数原样透传。

**双击失败后补的三处（都是真实踩到的）**

1. **不再每次跑 `uv sync`**：默认行为改成"`.venv\Scripts\python.exe` 存在就跳过同步"，
   只有首次部署或显式 `-ForceSync` 才联网同步。双击失败最常见的根因就是这一步（网络、代理、
   锁文件解析），而它和"能不能启动"本无关系。
2. **诊断落盘**：`Start-Transcript` 写 `ktem_app_data/logs/bootstrap-<时间>.log`；应用本身用
   `cmd /c "… app.py 2>&1" | Tee-Object -Append ktem_app_data/logs/app.log` 输出，
   窗口关掉也能事后读。注意 **PowerShell 5.1 的 `Start-Transcript` 抓不到原生命令的 stderr**，
   所以 uv 的调用改走 `cmd /c "uv … 2>&1"` 再 `Write-Host`，否则日志里只剩我们自己的 "uv sync failed"。
3. **原生 stderr 被当成致命错误**：脚本有 `$ErrorActionPreference = 'Stop'`，而应用启动时会往 stderr
   打 nltk/absl 警告；一旦写成 `& python app.py 2>&1 | Tee-Object`，PowerShell 把 stderr 包成
   ErrorRecord 并**直接终止脚本**（实测：窗口一闪、应用根本没起来）。修法是把启动也交给 `cmd /c`
   （见上一条），PowerShell 只看到 stdout 行。

验证：`cmd /c start.bat` 实测 15 秒内 `HTTP 200`，`app.log` 里有 `Running on local URL: http://127.0.0.1:7860`；
`-ForceSync` 的失败路径实测退出码 1，且 `bootstrap-*.log` 里含 uv 自己的
`× Failed to build …` / `Failed to update Windows PE resources`（沙箱限制，非脚本问题）。

**自动打开浏览器**：`app.py` 原本用 `launch(inbrowser=True)`，但 gradio 是在**服务刚起、还没监听**时就
`webbrowser.open`（而且某些宿主上 `webbrowser.open` 直接无声失败），用户看到的是"没有浏览器弹出"。
改为由启动脚本负责：

1. 新增 `KH_OPEN_BROWSER_ON_START`（默认 `true`，`python app.py` 行为不变）；
2. 脚本先设 `KH_OPEN_BROWSER_ON_START=0`（同一个浏览器只开一次，避免双标签页），
   再起一个后台作业**轮询** `http://127.0.0.1:<port>`，第一次拿到 200 才 `Start-Process <url>`；
   结果写 `ktem_app_data/logs/browser.log`；
3. 端口已被占用（已有实例在跑）时直接打开页面并退出，不再重复起一个必然失败的进程；
4. 端口跟随 `GRADIO_SERVER_PORT`，被占用时可换端口；`-NoBrowser` 可完全关闭。

验证：`cmd /c start.bat` 一次完整启动，`browser.log` 记录 `22:59:19 opened http://127.0.0.1:7860`，
同一时刻端口返回 `HTTP 200`——即"先就绪、后开页"，不会再出现空标签页。

### 5.7 切块粒度 A/B（ROADMAP B3）

原配置 `chunk_size=0` → 按"页"成块。新增两个配置项（默认 512/64）：
`FILE_INDEX_PIPELINE_SPLITTER_CHUNK_SIZE` / `..._CHUNK_OVERLAP`，改回 0 即恢复按页成块。

同一套 27 题、同一份四块扫描件，只改切块并重建该文件：

| 口径 | 块数 | Hit@1 | Hit@3 | MRR | 事实覆盖 |
|---|---|---|---|---|---|
| 按页成块（chunk_size=0） | 4 | 55.6% | 74.1% | 0.707 | 100% |
| **512/64** | 11 | **88.9%** | **96.3%** | **0.933** | 100% |
| 512/64 + 全库（含 1 万块表格） | 11 | 77.8% | 85.2% | 0.832 | 81.5% |

结论：**Hit@1 +33.3 个百分点**。注意块数只从 4 涨到 11（这份材料正文只有 2322 字符），
所以"块变多"本身解释不了 Hit@1 的提升——变化的是"第一条命中的就是含答案的那个块"。
副作用也实测了：块变细后，全库口径下大文件仍会摊薄（77.8% vs 88.9%），facts 81.5% vs 100%。

### 5.8 拒答闸门（ROADMAP B4）

**问题**：只要检索返回了东西，模型就会作答——哪怕内容完全不相关。原来的"没有可检索文件才提示"
只挡住了空集合，挡不住"检索到了不相干的内容"。

**实现**（`libs/kotaemon/kotaemon/abstain.py` + `libs/ktem/ktem/reasoning/simple.py`）：

1. 纯逻辑 `should_refuse(scores, threshold)`：没有召回 → 拒答；只有关键词命中（分数是
   `-1` 哨兵，见 `vectorindex.py`）→ 不拒答（没有相似度可判）；否则最高相似度低于阈值 → 拒答；
   `threshold <= 0` 关闭闸门（保留旧行为，可回退）。
2. 三条对话路径（`FullQAPipeline`、分解式主问题、分解式子问题）在检索后立刻判定，命中即输出
   "知识库没有依据 + 下一步建议"，**不再调用模型**。
3. 被拦截的查询写入 `ktem_app_data/abstained_queries.jsonl`（时间、问题、最高分、阈值），路径可用
   `KH_ABSTAIN_LOG` 覆盖。
4. 阈值 `KH_ABSTAIN_SCORE_THRESHOLD`（默认 **0.45**），用离线集校准：

| 阈值 | 无答案题正确拒答 | 可答题误拒 |
|---|---|---|
| 0.42 | 75.0% | 0% |
| **0.45** | **91.7%**（11/12） | **0%**（0/27） |
| 0.53 | 100% | 会误伤（最低正分 0.473） |

> 12 题里唯一没被拒的是「教务处的电话是多少？」（最高分 0.532）：它和语料里的电话号码段落
> 语义上确实接近，要拒掉它就必须把阈值抬到 0.53，而那会开始误伤正常题。**91.7% / 0% 是这条
> 曲线上的最优点**，所以阈值定为 0.45——不是拍脑袋的值。

**局限（写清楚，免得被追问）**：这道闸门只看检索分数，不做语义判断；同义但低分的问法会被拒，
"看似相关其实回答不了"的题仍可能通过。更彻底的做法是答案后校验（C 组待做）。

**表格语料的误拒与修正（2026-10-17 补）**：用户上传 `某班级社会实践完成情况表.xlsx` 后问
「李同学的社会实践完成了吗」——界面右侧**明明高亮显示了李同学那一行**，却被拒答
（best match 0.38 < 0.45）。原因不是检索失败，而是**单一阈值是用散文语料标定的**：
一行 `24405010001,李同学,8,24,2025上半年8学时` 与自然语言问题的向量距离天然偏远。

修正为"罕见实体词 + 表格式行"的二级判定：

1. `entity_terms()`：问题里所有 3 字 CJK 窗口（人名/课程名）与 3+ 位拉丁数字 token（学号/编号）；
2. `specific_term_evidence()`：某个实体词**逐字出现**在某条召回内容的**表格式行**里
   （`row_looks_tabular`：≥3 个字段、且 ≥60% 字段含数字），并且**只出现在少数召回块中**
   （≤30%，否则是主题词而不是某一行）；
3. `should_refuse(..., documents, question, term_floor)`：分数在 `[KH_ABSTAIN_TERM_FLOOR, 阈值)` 之间
   且有上述证据时**不拒答**；默认 floor = **0.33**，设 0 可关闭该放宽；
4. 被拒记录里加了 `reason` 字段，便于事后审计。

关掉"表格式行"这一条会在**散文**里误命中：无答案集里「图书馆一次最多可以借几本书？」的
`图书馆` 出现在积分细则里，一度把正确拒答从 91.7% 拉到 83.3%；加上"表格式行"后回到 **91.7%**。

实测（同一份 xlsx，用界面「在文件中搜索」的 file-id 口径检索）：

| 问题 | 最高分 | 实体词 | 旧规则（只看 0.45） | 新规则 |
|---|---|---|---|---|
| 李同学的社会实践完成了吗 | 0.382 | ✓ | 拒答 ❌ | **回答** ✅ |
| 周大鹏的学时是多少 | 0.409 | ✓ | 拒答 ❌ | **回答** ✅ |
| 吴晓峰的学时 | 0.375 | ✓ | 拒答 ❌ | **回答** ✅ |
| 郑美玲的社会实践完成了吗 | 0.395 | ✗ | 拒答 ❌ | 拒答 ❌ |
| 孙小勇完成了吗 | 0.328 | ✓ | 拒答 ❌ | 拒答 ❌（低于 floor） |
| 陈晓东的学时是多少 | 0.417 | ✗ | 拒答 ❌ | 拒答 ❌ |
| 陈志强…（表里没有） | 0.401 | ✗ | 拒答 ✅ | 拒答 ✅ |
| 李同学的体重是多少（属性没有） | 0.289 | ✓ | 拒答 ✅ | 拒答 ✅ |

可答题误拒 **6/10 → 3/10**，不可答题 0 误放行；无答案集回归仍 **91.7%**。
剩下 3 题不是闸门的问题：它们那几行**根本没被召回**（该文件 6 块只返回 3 块），属于"按文件配额 / top_k"
的召回召回问题。

**拒答文案已本地化**：两段模板走 `tr()`，中文词表新增对应条目，界面为 `zh` 时输出
「知识库中没有回答这个问题所需的依据（最佳匹配得分 0.38，低于阈值 0.45）」而不是英文原文
（之前是英文，属于"界面中文、提示英文"的不匹配）。

### 5.9 重排闭环（ROADMAP B2）

**问题**：默认重排器是 Cohere，没有 API key。`run()` 会打印 "Skipping rerankings" 然后**原样返回**——
界面显示"开着重排"，实际什么也没做。这与 §2.7–§2.10 是同一类"配置写了但没生效"。

**为什么不是 cross-encoder**：roadmap 首选本地 ONNX cross-encoder，但本机 `fastembed` 是 0.4.2
（没有 `TextCrossEncoder`），且 HuggingFace 模型下载在本机不通。于是先做**不需要任何模型/网络**的本地词法
重排，作为"重排到底值不值得上"的对照组，也为以后换 cross-encoder 留下同一套测量口径。

**实现**

1. `libs/kotaemon/kotaemon/rerankings/local_lexical.py`：中文字符 bigram + 拉丁词切分，
   按"问题词被覆盖的比例"给每个块打分；**只重排、默认不丢块**（丢块会把一次可恢复的漏召回变成永久漏召回）。
2. 分数处理：**保留原检索相似度**，词法分写进 `metadata["rerank_score"]`——拒答闸门（§5.8）是按相似度
   校准的，重排把分数改掉会静默让那个阈值失效。
3. `BaseReranking.is_available()` + `resolve_reranker()`：配置了但跑不了的重排器（Cohere 无 key）
   **自动回退**到本地词法重排，并打印一行说明。这一条同时修掉了"重排显示已开、实际空转"的缺陷。
4. `KH_RERANKINGS["local"]` 注册（新库会出现在「资源 → 重排」里；老库需重新播种才列出，见下）。

**实测**（27 题，同一套评测，`--rerank off` / `on`；`on` 即回退后的本地词法重排）

| 口径 | 配置 | Hit@1 | Hit@3 | MRR | facts | P50 | P95 |
|---|---|---|---|---|---|---|---|
| 单文件（11 块） | off | 88.9% | 96.3% | 0.933 | 100% | 470 ms | 555 ms |
| 单文件（11 块） | **on** | 88.9% | 96.3% | 0.933 | 100% | 467 ms | 677 ms |
| 全库（含 1 万块表格） | off | 77.8% | 85.2% | 0.832 | 81.5% | 1053 ms | 1230 ms |
| 全库（含 1 万块表格） | **on** | 77.8% | **88.9%** | **0.847** | 81.5% | 1303 ms | 1615 ms |

读法：
- 小语料上**没有收益**（前 10 条本来就排对了），P95 略升——如实记录，不吹；
- 全库上 **Hit@3 +3.7 个百分点、MRR +0.015**，代价是 P50 +24%（+250 ms）；
- Hit@1 不变，说明词法重排能纠正"第 2–3 名里的顺序"，纠正不了"第 1 名就错了"——
  那需要语义重排（cross-encoder）或 §5.7 的切块/检索配额。

**怎么启用/换回**：不需要动代码——默认（无 Cohere key）就会回退到本地重排；希望完全关掉重排就把
「资源 → 文件集合」里的 `Use reranking` 关掉；装了 Cohere key 则自动用 Cohere。
老数据库的模型池只在建库时播种，所以 `local` 需重新播种才会出现在下拉框（删掉 `reranking` 表行重启即可）。

### 5.10 成本、延迟与查询 trace（ROADMAP C3 + C4）

**动机**：回答过程是个黑盒。`use_llm_reranking` 默认开着，意味着**每个召回块各调一次 LLM 打相关性分**，
但没人知道这为每题多花了多少次调用、多少 token；出问题时也说不清"这次回答为什么是这样"。

**实现**

1. **用量记账**（`libs/kotaemon/kotaemon/llms/usage.py`）：进程级线程安全计数器；
   `BaseChatOpenAI` 在非流式响应（`prepare_output`）与**流式最后一帧**（`stream_options.include_usage`，
   不支持该参数的 provider 会自动去掉参数重试）记账。
2. **每题 trace**（`libs/ktem/ktem/utils/trace.py`）：JSONL 一行一题，字段
   `question / retrieved / top_score / reranked / abstained / answer_chars / total_ms / calls /
   prompt_tokens / completion_tokens / total_tokens`；由 `FullQAPipeline.stream` 在正常作答与拒答两条路径都写。
   开关 `KH_QUERY_TRACE`（空=关，`1`=`ktem_app_data/query_trace.jsonl`，其它=路径）；写失败只记日志，绝不影响作答。
3. **聚合报告**（`tools/trace_report.py`）：请求数、拒答率、端到端 P50/P95、每题 token / LLM 调用数 / 召回块数、
   启用重排比例；`--last N` 可只取文件末尾 N 条（两个 A/B 跑进同一文件时用）。

**实测**（同一 6 题、真实 DeepSeek 调用、单文件范围）

| `use_llm_reranking` | 每题 LLM 调用 | 每题 token（6 题合计） | 端到端 P50 | P95 |
|---|---|---|---|---|
| 关 | **1.0** | **3291（19744）** | 2564 ms | 3530 ms |
| 开（原默认） | **11.0** | **9043（54257）** | 2955 ms | 4027 ms |

**决策**：把 `use_llm_reranking` 的默认值改成**关**（`USE_LLM_RERANKING=false`，勾选框仍可打开）。
理由：它每题多花 **10 次 LLM 调用 / +5752 token（+175%）**，而作用只是给证据面板按 LLM 相关性排序
+ 触发低相关提示；关掉后证据面板仍按检索顺序展示，行为降级但不失效。省下来的调用留给答案本身。

**怎么复现**

```powershell
$env:KH_QUERY_TRACE="$env:TEMP\trace-off.jsonl"
# 用 tools 里的探针或直接对话几题，然后：
.\.venv\Scripts\python.exe tools\trace_report.py --trace $env:TEMP\trace-off.jsonl
```

**局限**：① 只有 provider 返回 usage 时 token 才准（通义/DeepSeek 都支持，不支持则记 0，不做估算）；
② trace 是**进程级 delta**，同一进程里并发的两题会各自包含时间窗口内的调用，不适合高并发场景；
③ 端到端延迟包含答案生成，不是纯检索延迟（纯检索延迟见 §5.7/§5.9 的评测表）。

### 5.11 `.pptx` 本地读取器（ROADMAP C5）

`.pptx` 之前和 `.docx` / `.xls` 走同一条 `unstructured` 路线（要系统 `libmagic`，首次还联网取资源），
在本机属于"上传了但没进索引"。这次换成纯本地读取器：

- `libs/kotaemon/kotaemon/loaders/pptx_loader.py`：`python-pptx` 读取，**一页一张 Document**：
  形状文本按顺序、表格渲染成 CSV、**备注页**（speaker notes）一并带上；
  `page_label` = 幻灯片序号，于是引用面板和 PDF 一样显示「第 N 页」，元数据契约不变。
  纯图片页跳过；整份没有文字时仍返回 1 条空文档——这样"空幻灯片"和"解析失败"在文件列表/`doctor` 里可区分。
- 依赖：`libs/kotaemon/pyproject.toml` 增加 `python-pptx>=1.0,<2`（uv.lock 同步：新增
  `python-pptx 1.0.2` + `xlsxwriter 3.2.9`，共 +37 行）。
- 路由：`KH_DEFAULT_FILE_EXTRACTORS[".pptx"]` 由 `unstructured` 改为 `PptxReader()`。
- 测试：`libs/kotaemon/tests/test_pptx_reader.py` 6 例（幻灯片分页/表格 CSV/备注/extra_info/空稿/文件不存在），
  **.pptx 由 python-pptx 在测试里现场生成**，仓库里不放二进制夹具；`test_ingestor.py` 再断言一次路由。
- `.doc`（老二进制 Word）仍留在 `unstructured`：python-docx 不支持它，本机也没有 LibreOffice，
  无法诚实地宣称支持。

### 5.12 引用"预览原文"链接失效的修复

**现象**：重建索引或启动自愈之后，引用面板的「预览」打不开，日志里反复刷
`pdf-path: …\repair_src\xxx.xls does not exist`。

**根因**（两层）：
1. 存储副本按**裸内容哈希**落盘（没有扩展名），于是块的 `file_path` 只能指向当时的**工作副本**——
   上传缓存、或重建工具的 `*_src` 目录；工具结束时会删掉那个目录，路径就悬空了。
2. 即使指向存储目录也不够：Gradio 的 `/file=` 只允许 `GRADIO_TEMP_DIR` 与 assets，
   存储目录不在白名单里，会 403。

**修复**
1. `stored_file_name()`：副本命名为 `<hash><扩展名>`，`Source.path` 同名，**不多存一份**；
   索引时把 `metadata["file_path"]` 指向这份副本（有扩展名，PDF 阅读器能识别）。
2. `app.py` 的 `allowed_paths` 加入 `KH_FILESTORAGE_PATH`，`/file=` 可以取到它。
3. `Render.preview` 只对 **PDF** 检查文件是否存在并按需告警——非 PDF 本来就不会进阅读器，
   以前每渲染一条引用就打印一次，把日志淹了。

**验证**
- 重建那份 PDF 后：块元数据 `file_path = …\user_data\files\index_1\<hash>.pdf`、`os.path.isfile` 为真；
- `/file=<存储副本>` 返回 **HTTP 200 / 14 MB / application/pdf**；旧临时路径按预期 **403**；
- 测试 `libs/ktem/ktem_tests/test_stored_paths.py` 8 例（命名、路径穿越、旧裸哈希兼容、
  PDF 有/无文件、非 PDF 不告警）。

**局限**：老数据里裸哈希的副本仍然可用（`repair`/`reindex` 都能读），但其块的 `file_path` 仍指向旧路径，
**重建一次**才会更新；新上传的文件立刻正确。







---

## 六、环境适配（非项目代码改动，但换机器时需知道）

### 6.1 Python 版本必须用 3.10，不能用 3.13

上游把 `onnxruntime` 钉在 `<1.20`（FastEmbed 依赖它）。查 PyPI 元数据，
`onnxruntime 1.19.2` 只发布了 **cp38 / cp39 / cp310 / cp311 / cp312** 的 wheel，
**没有 cp313，也没有源码包**，因此在 Python 3.13 上无法安装。
uv 可自动下载 Python 3.10.20。

### 6.2 在受限沙箱环境中运行时需重定向临时目录

若 Python 进程运行在**低完整性级别**（沙箱会把工作区内的可执行文件降级），
它将无法写入 `%TEMP%` 和未被降级标记的子目录。这会同时打断两件事：

- Gradio 在组件源码旁生成 `.pyi` 存根；
- LanceDB 构建全文索引时写入临时文件。

规避方式（仅在此类受限环境需要，普通终端不需要）：

```powershell
$env:TMP  = "<仓库>\ktem_app_data\tmp"
$env:TEMP = "<仓库>\ktem_app_data\tmp"
$env:THEFLOW_TEMP_PATH = "flow_tmp"
```

### 6.3 磁盘占用与清理（本机实测）

仓库目录一度占到 **7.1 GB**，其中绝大部分是可再生成的缓存。清理后降到 **约 2.0 GB**
（`.venv` 1.92 GB + 数据 0.09 GB）：

| 项目 | 清理前 | 处理 | 说明 |
|---|---|---|---|
| `ktem_app_data/fastembed_cache` | 3.70 GB | **全部删除** | 三个本地模型：mpnet 1.05 GB、e5-large 2.10 GB、MiniLM 0.48 GB。改用通义 API 后不再需要 |
| `.venv/Lib/site-packages/torch` | 1.23 GB | 删除 | 由 `sentence-transformers` 引入；本项目向量化走 FastEmbed(ONNX)，运行时完全不 import |
| `ktem_app_data/tmp` | 127 MB | 清空内容 | pytest / nltk / 上传临时文件 |
| `flow_tmp`、`.theflow`、`data-gym-cache` | 46 MB | 删除 | theflow 与 tiktoken 的运行时缓存 |

**删 torch 前做了验证**（不是试错）：先改名而非直接删，用真实进程跑一遍
`ktem.main` / `ocr_pdf_loader` / `fastembed` / `rapidocr_onnxruntime` 的导入链，
再完整启动应用确认页面 200，才真正删除。注意 `uv sync` 会把它装回来，
想长期排除可加 `--no-install-package torch`。

> **不在清理范围内**：`user_data/`（上传的原始文件、sqlite、LanceDB、Chroma）、
> `gradio_tmp/`（引用面板的 PDF 预览链接指向它，删了「预览」会失效）、`.git`（13 MB）。
> 换成通义向量后，`fastembed_cache` 整目录已删除（省 1.05 GB）；需要离线兜底时
> 再拉一次即可（首次使用自动下载）。

---

## 七、复现与验证清单

### 7.1 启动

```powershell
# 首次
uv python install 3.10
uv sync --python 3.10 --no-install-package llama-cpp-python

# 配置：复制 .env.example 为 .env，填入 DEEPSEEK_API_KEY 等

# 启动
.\.venv\Scripts\python.exe -X utf8 app.py
```

访问 `http://127.0.0.1:7860`，默认账号 `admin` / `admin`。

### 7.2 验证检索是否真的生效

1. 上传一份**内容可核实**的文档（例如含明确数字的内部制度），建立索引。
2. 在 Chat 页直接提问一个**文档里写了、但公开资料里是别的答案**的问题。
   > 这一点很关键：如果问题问的是「差旅住宿标准」这种公开知识，
   > 模型凭训练记忆也能答得像模像样，**看不出检索有没有生效**。
3. 检查引用栏：应显示你的文件名与相关度得分，而不是 `No evidence found.`；回答中的数字应与文档一致。

### 7.3 回归检查

- `Search In File(s)` 模式 + 勾选具体文件 → 仍应正常召回。
- 上传一份**文档中不存在**的问题 → 相关度得分应明显偏低，不应给出笃定答案。
- `pytest libs/kotaemon/tests/test_ocr_pdf_reader.py libs/ktem/ktem_tests/test_i18n.py
  libs/ktem/ktem_tests/test_file_selector.py libs/ktem/ktem_tests/test_conversation.py
  libs/ktem/ktem_tests/test_mcp_manager.py -q`
  → 全绿（当前 **88 passed** = 7 + 44 + 10 + 14 + 13）。
  > `test_qa.py` 是上游自带、无法收集的用例（`from index import …` 解析不到），与本次改动无关。
  > 跑测试前先停掉应用：sqlite / LanceDB 被占用时 pytest 会长时间无输出。
- **扫描件检索**：上传一份扫描版 PDF，看索引日志里是否出现
  `Using reader OCRPDFReader(...)` 与 `OCR used for N page(s)`；
  再问一个正文细节问题，答案应带 `[第 N 页]` 引用。数字版 PDF 不应触发 OCR（`ocr=False`）。
- **检索评测**（先停应用，二者共用库文件）：

  ```powershell
  .\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json `
      --out tools\eval\results.md --json tools\eval\results.json
  ```

  基线：Hit@1 59.3% / Hit@3 74.1% / MRR 0.702 / 事实覆盖 81.5%（详见 §9.3）。
  评测集的 `corpus` 字段已脱敏，在本地真实语料上运行时加 `--corpus "真实文件名"`。
- **词表入库**：把 `ktem_app_data/i18n/` 改名（模拟全新 clone）后再启动，
  界面应仍为中文（来自 `libs/ktem/ktem/assets/i18n/zh.json`）。
- 界面语言：`KH_UI_LANGUAGE=en` 启动可还原英文界面，用于确认本地化层是纯附加的
  （此时 `tr()` 与通知钩子都退化为恒等函数，词表文件也不会被读取）。
- 运行时层逐项核对：
  - 页脚应显示 `版本：0.12.0`，而不是 `version: 0.12.0`；
  - 引用栏应显示 `图像 来自 [第 1 页] … [得分：0.0] [预览]`、`相关性分数`、`向量存储得分：`；
  - 任一点击会弹 toast 的操作（如保存设置）应弹中文提示；
  - 会话标题生成、追问建议应跟随回答语言。
- **必须在浏览器里看一次**（接口测试覆盖不到前端）：打开首页确认登录框出现、能登录，
  且浏览器控制台无 `SyntaxError`。这是 §3.5 那次「整站白屏」的唯一可靠发现方式。
- 词条缓存：`python -m ktem.utils.i18n stats --language zh` 应显示 `336 entries`；
  删除 `ktem_app_data/i18n/zh.json` 后首次启动仍是英文，需先跑 §3.7 的 build 命令重建。
- **UI 视觉层（§5.24）**：

  ```powershell
  $env:TMP = "$PWD\ktem_app_data\tmp"; $env:TEMP = $env:TMP
  $env:PYTHONPYCACHEPREFIX = "$env:TMP\pycache"
  .\.venv\Scripts\python.exe -X utf8 -m pytest libs\ktem\ktem_tests\test_ui_theme.py -q
  ```

  → **14 passed**；启动日志应为 `UI language 'zh': ... 352 catalog entries, 19 missing`；
  `/config` 里能查到 `app-header`/`app-tabs`/`chat-workspace`/`login-card`，
  `theme` 为 `citeask`；首页源码含 `--ui-bg:` 与 `ktem-theme`。
  > Windows 下 `-X utf8` 不可省（否则 Gradio 生成 `.pyi` 时按 GBK 解码源码直接报错）；
  > 受限沙箱还要把 `TMP`/`TEMP` 指向 `ktem_app_data/tmp`，否则 pytest 的 `tmp_path`
  > 会在既有的 `pytest-of-HP` 上触发 ACL 的 `PermissionError`。`test_i18n.py` 的
  > 19 个 setup error 改动前就存在，不属于本改动。

---

## 八、简历表述建议

### 8.1 一句话版本

> 在开源 RAG 代码库上完成中文文档问答的产品化与全栈改造：修复三类"配置了但没生效"的数据入口缺陷，
> 建立只跑检索层、零 token 成本的评测并据此把单文件 Hit@1 从 59.3% 提到 88.9%，
> 同时把 Gradio 单页替换为 React 18 + FastAPI（39 个接口、SSE、57 个 API 测试）。
> 自有提交 46 个、源文件改动 343 个（不含构建产物与 lock）。

### 8.2 分点版本（STAR）

- **背景/目标**：把一份扫描版制度 PDF 变成可逐页引用的知识库；对话走 DeepSeek，向量化可走
  通义 API 也可本地 ONNX，要求离线可兜底、不把 embedding 成本绑死在一家服务上。
- **缺陷定位（检索静默失效）**：引用栏一直是 `No evidence found.`，模型却仍能作答。沿着
  「UI 选择 → `doc_ids` → 检索器」的链路定位到两处叠加状态缺陷：选择器默认值不在可选项集合内，
  以及全库检索分支依赖只在手动交互后才刷新的陈旧 `gr.State`；把选择器抽成纯函数，补 10 个不变量用例，
  并覆盖 File 索引与 3 个 GraphRAG 分支。
- **数据入口（扫描件 OCR）**：扫描 PDF 4 页只抽出 209 字符，而且全是标题和 `Page thumbnail` 图片块。
  导出索引块确认问题在数据入口，不在检索算法；实现按页决策的 `OCRPDFReader`（文字层 ≥200 字符直接用，
  否则 200 DPI 渲染 + 本地 PP-OCR，失败保留原文字层），同一文件正文恢复到 **2322 字符**，
  回答带 `[第 2 页]` 引用。
- **评测驱动优化**：自建只跑检索层、零 token 成本的评测（私有 27 题 + 12 道无答案题；公开 5 页
  虚构语料 + 9 题验证链路，公开 9 题实测 Hit@1 **87.5%** / MRR **0.900**），用同一套题完成
  切块 A/B（512/64）、本地词法重排、拒答闸门与向量模型选型：单文件 Hit@1 **59.3% → 88.9%**、
  MRR **0.702 → 0.933**，无答案题拒答 **91.7%**，检索 P50 约 **1.6 s**。
- **全栈重构**：把 Gradio 单页替换为 React 18 + TypeScript + Vite + FastAPI `/api/v1`：
  **39 个接口**、SSE 流式回答、HttpOnly HMAC 会话、管理员 RBAC、供应商表单由服务端 `describe()`
  生成；保留 `/legacy` 与 `KH_WEB_UI=0` 回滚。**57 个 API 测试 + 43 个前端单测**，
  首屏 JS **272.11 kB** gzip。
- **工程化与可观测性**：**399 个 Python 用例 + 43 个前端单测**进 GitHub Actions；一键启动、
  `doctor` 自检、查询 trace 与 token 记账；量化 LLM 重排代价（开 11 次/9043 token，关 1 次/3291 token）
  并默认关闭；索引失败回滚 + 启动自愈，避免"文件在列表里但检索不到"的幽灵状态。
- **本地化**：Gradio 4.39 无 i18n 机制，实现「采集 → 外部翻译 → 词表缓存 → 回写」流水线，
  **336** 条词条 / **296** 处标签，覆盖 Python 运行时、约 50 条事件弹窗和浏览器端三类通道，
  译文不落源码；并让模型回答语言跟随界面语言。

### 8.3 与上游的边界（面试必须能说清）

仓库包含上游 kotaemon 的代码，上游提供了 RAG 骨架与经典 Gradio 页面；本仓库的 47 个提交、
343 个源文件改动集中在上面的四块（检索/OCR/评测/全栈/工程化）。被问"哪部分是你写的"时，
直接按 commit 或 `MODIFICATIONS.md` 的文件清单回答，不要声称上游框架也是自己从零写的。
简历里只写"在开源 RAG 代码库上完成..."，把重点放在可验证的改造与数字上。

### 8.4 可延伸的面试话题

| 话题 | 可讲的内容 |
|---|---|
| RAG 幻觉治理 | 为什么「检索召回为空」比「检索召回了错的内容」更危险——模型不会报错，只会自信地编 |
| 评测驱动迭代 | 为什么必须先有「只跑检索层、零成本」的评测，才能谈换向量模型、开重排、改切块——否则所有优化都是感觉 |
| 指标读法 | 语料只有 4 个块时 Hit@5 必然 100%，区分度在 Hit@1/MRR；事实覆盖率 100% 说明问题在排序而非召回 |
| 验证策略 | 为什么必须用「文档里有、公开知识里也有但答案不同」的问题来验证检索，而不是随便问一个 |
| 可测性设计 | 为什么把「默认模式」抽成常量并断言它属于可选集合，比端到端兜底更早暴露缺陷 |
| CI 设计 | 399 个 Python 用例 + 43 个前端单测分两个 job；为什么把新增模块的覆盖率做成报告而不是一刀切门槛 |
| 全栈迁移 | 为什么先抽 `services`（不 import gradio）再加 `api`：路由只做鉴权/序列化，业务可脱离 UI 单测；SSE 用 `asyncio.Queue` 桥接同步管线 |
| 评测边界 | 公开 9 题只验证链路，私有 27 题才是效果数字；简历里必须带语料口径，不把私有数字说成可复现 |
| 回滚设计 | 为什么保留 `/legacy` 与 `KH_WEB_UI=0`：迁移期出问题一条环境变量切回，不靠"回滚代码" |
| 依赖治理 | `onnxruntime<1.20` 无 cp313 wheel 导致的 Python 版本锁定；无 Windows wheel 的可选依赖如何安全排除 |
| 配置系统设计 | 上游「按环境变量推导默认值」的设计在多 provider 组合下会失效，显式收敛 vs 隐式推导的取舍 |
| i18n 安全边界 | 汉化最大的风险不是漏翻，而是把「值」当「文案」翻了。讲清如何用属性白名单 + `(标签, 值)` 分离，把改坏业务数据的概率降到零，并写成不变量测试 |
| 无框架支持时的取舍 | 为什么选「服务端构建后遍历改写」而不是「客户端 DOM 替换」——前者无首屏闪烁、可确定性验证、可单测 |
| 机器翻译的工程化 | 三个真实坑：免费接口 429 / 无超时会永久挂起（用 socket 超时 + 并发解决）、Markdown 结构被破坏（结构校验 + 拒绝译文）、逐条翻译的上下文丢失（改批量 + 冲突检测） |

---

## 九、检索评测与开箱即用

### 9.1 为什么单独做评测

前面所有验证都是「问一句、看答得对不对」——能发现坏掉，但**无法衡量好坏**，也无法对比
改造前后（OCR 前后、换向量模型前后、开重排前后）。

因此补了一层**只跑检索、不调用任何模型**的评测：零 token 成本，可反复跑，改动前后直接对比。

### 9.2 设计

- [tools/eval_retrieval.py](tools/eval_retrieval.py)：跳过 Gradio UI 直接构建检索管线
  （`FileIndex.get_retriever_pipelines` 依赖只在 UI 构建后才存在的选择器组件，所以这里
  按同样方式手工装配 DS/VS），对每个问题取 top-k 块；
- 三个指标：
  - **Hit@k**：期望页码是否出现在前 k 个块里；
  - **MRR**：第一个命中块名次的倒数，区分「排第 1」和「排第 4」；
  - **关键事实覆盖率**：期望事实是否出现在**送给模型的文本**里 —— 能抓到「页对了但块不对」；
- 评测集 [tools/eval/zh-points-rules.json](tools/eval/zh-points-rules.json)：27 条问题，
  覆盖 4 页的全部章节，每条带期望页码与关键事实；语料文件名与机构信息已脱敏
  （本地跑真实语料时用 `--corpus "真实文件名"` 覆盖）；
- 匹配细节：文件名比较忽略标点（Gradio 上传会把 `（修订版）` 洗成 `修订版`，
  严格比较会全部不匹配）；文本比较去掉所有空白（OCR 会在任意位置换行）。

### 9.3 基线（换向量模型后）

| 指标 | 值 |
|---|---|
| 问题数 | 27 |
| 语料 | 2 个文件 / 8 个块（目标 4 块 + 干扰 4 块） |
| Hit@1 | 59.3% |
| Hit@3 | 74.1% |
| Hit@5 | 81.5% |
| MRR | 0.702 |
| 关键事实覆盖率 | 81.5% |

**读法很关键**：`top_k=5` 时，库里**多出的无关文档会摊薄命中**。单文件语料（4 块）时
Hit@5 = 100%、MRR = 0.739；加入第二个文件（共 8 块）后 Hit@5 → 81.5%、MRR → 0.702，
而 Hit@1 基本不变（59.3%）——说明检索本身能排到前面，问题是"名额被干扰块分走"。
这正好给出下一步（重排 / `top_k` 调参）的量化目标。

> 题库从 30 题精简为 27 题后，指标由原有逐题结果重算（删掉的 3 题不含检索行为变化，
> 因此重算与重跑等价）；§9.4 的模型对比表仍是 30 题版本的历史实测，两套口径不可直接相减。

### 9.4 评测驱动的优化一：向量模型选型

初版默认是 `paraphrase-multilingual-MiniLM-L12-v2`（384 维，2020 年的模型）。在 FastEmbed 0.4.2
支持的模型里，可用的多语言/中文候选只有三个；再加上通义（DashScope）的 API 模型，逐一试
（下表为**题库 30 题版本**上的实测）：

| 模型 | 维度 | 本地体积 | Hit@1 | Hit@3 | MRR |
|---|---|---|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2`（初版） | 384 | 0.22 GB | 36.7% | 73.3% | 0.589 |
| `paraphrase-multilingual-mpnet-base-v2`（本地，离线兜底） | 768 | 1.0 GB | 60.0% | 80.0% | 0.739 |
| **`text-embedding-v3`（通义 DashScope，现默认）** | 1024 | 0（API） | **60.0%** | 76.7% | 0.736 |
| `multilingual-e5-large`（带 E5 前缀） | 1024 | 2.24 GB | 53.3% | 73.3% | 0.683 |
| `multilingual-e5-large`（不带前缀） | 1024 | 2.24 GB | 46.7% | 70.0% | 0.642 |

三个结论：

1. **只换一个模型名，Hit@1 +23.3pp**（36.7% → 60.0%，30 题口径）。这也是先做评测的价值：
   没有基线就没法说"更强"，更没法在多个候选里选。
2. **通义 v3 与本地 mpnet 基本持平**（Hit@1 均 60.0%，MRR 0.736 vs 0.739），
   但通义不占本地磁盘、无需下载 —— 考虑到本机被本地模型撑到 3.7GB，
   最终**默认走通义**，本地 mpnet 保留为离线兜底。
3. **E5 系列必须带前缀**：同一个模型，带 `query: ` / `passage: ` 比不带高 6.6pp。
   而框架原本把查询和文档一起送进同一个 `embed(text)` 接口，丢掉了这个区分。

修复与实现：

- 给 `FastEmbedEmbeddings` 补 `query_prefix` / `passage_prefix`，按调用形态自动加前缀 ——
  该代码库中**查询传单个字符串、建索引传文档列表**（`VectorRetrieval` / `VectorIndexing`），
  所以这个区分是可靠的；
- 通义走 **OpenAI 兼容接口**，因此不需要新写 provider，只需在 `flowsettings.py` 里注册一个
  `OpenAIEmbeddings` 实例（`base_url=https://dashscope.aliyuncs.com/compatible-mode/v1`）；
- 顺带发现 `OpenAIEmbeddings.invoke` 是**把所有文本塞进一次请求**，而通义单次上限 25 条，
  语料一多就会 400 —— 补了 `batch_size` 分批，同时兼容 OpenAI 的海量上限；
- `.env` 里有 `DASHSCOPE_API_KEY` 就默认用通义，没有则自动回落到本地 FastEmbed。

> 注意：provider 池**只在数据库表为空时**才从 `flowsettings` 播种，所以已装好的实例
> 必须显式改库（本次是更新 `embedding` 表的 default 标记）。另外 API key 会被写进
> `ktem_app_data/user_data/sql.db` 的 provider spec（上游既有行为，该目录已被 git 忽略）。

### 9.5 评测暴露的剩余项

**重排是空配置**：`use_reranking=True`、默认 Cohere，但没有 API key —— 每次检索只打印
`Cohere API key not found. Skipping rerankings.` 然后原样返回。换成本地 ONNX
cross-encoder 后，同样用 Hit@1 / MRR 量化收益。这是下一个评测驱动的优化项。

### 9.6 换模型后如何重建索引

换向量模型必然要重建索引：不同模型的维度不同（384 / 768 / 1024），旧向量无法复用。
为此补了 [tools/reindex_corpus.py](tools/reindex_corpus.py)：

```powershell
.\.venv\Scripts\python.exe tools\reindex_corpus.py --drop            # 丢库 + 全量重建
.\.venv\Scripts\python.exe tools\reindex_corpus.py --match "积分细则"  # 只重建匹配的文件
.\.venv\Scripts\python.exe tools\reindex_corpus.py --add 某文件.pdf    # 补录一个新文件
```

实现上踩了两个坑：

- **原始文件没有扩展名**：文件存储按内容哈希保存（`files/index_1/<hash>`），而读取器是按扩展名
  选的，所以重建前要按原文件名复制一份出来；
- **异常被吞掉**：`IndexDocumentPipeline.stream()` 内部 `except Exception` 后只发一个
  `status: "failed"` 的文档，直接 `for _ in stream(): pass` 会误报成功 —— 必须检查
  `channel == "index"` 的文档内容。这个坑也是"重建后索引全空却显示成功"的原因。

### 9.7 开箱即用：词表入库

之前词条缓存只在 `ktem_app_data/i18n/zh.json`（git 忽略），**别人 clone 下来是英文界面**。

现在 `load_catalog()` 合并「仓库内置词表 + 用户词表」，**用户词表逐条覆盖**，
所以既能让新克隆开箱即中文，又能让使用者单独改某一条而不动仓库：

```python
# 仓库：libs/ktem/ktem/assets/i18n/zh.json（生成后入库）
# 用户：ktem_app_data/i18n/zh.json（覆盖仓库同名词条）
catalog = load_catalog("zh")
```

配套命令：

```powershell
.\.venv\Scripts\python.exe -m ktem.utils.i18n stats  --language zh   # 分别显示仓库/用户/合并条数
.\.venv\Scripts\python.exe -m ktem.utils.i18n bundle --language zh   # 把用户词表同步进仓库
```

验证：把用户词表路径指向不存在的文件（模拟全新 clone），合并后仍有 **336 条**，
`tr("[Page {}]")` → `[第 1 页]`、`tr("Relevance score")` → `相关性分数` 均正确 ✅

> 注意：本机受限沙箱里 `bundle` 写 `libs/` 会被权限拒绝（低完整性进程不能写该目录），
> 普通终端执行正常；沙箱内改用文件复制即可。

### 9.8 让评测在干净 clone 上可跑通：自带示例语料（2026-10-18）

**问题**：README 首页写着 Hit@1 88.9%，但仓库里**没有那份语料**——评测集的 `corpus` 是
一个脱敏文件名，新环境跑出来是：

```
语料块数 = 0（Hit@k 的上限受此限制）
Hit@1 = 0.0%
```

这不是"数字错了"，而是"数字没法被验证"。简历项目最怕这一条：面试官 clone 下来跑不出
你写的数。

**为什么不能直接提交真语料**：那是一份含同学姓名、学号、班级的成绩表，属于别人的个人信息，
不能进公开仓库。所以补一份**虚构但同结构**的语料：

- `tools/eval/fixtures/points-fixture.pptx`：5 页（封面 / 学业加分 / 实践加分 / 理论考试+表格 /
  减分与说明），内容全虚构；选 PPTX 是因为它的文字在 XML 里、**不需要 CJK 字体**就能生成，
  且项目的 PPTX 读取器本来就把 `page_label` 设成页码，页码级指标不会退化成"全是第 1 页"；
- `tools/eval/make_fixture.py`：确定性生成脚本（`python tools/eval/make_fixture.py` 重新生成）；
- `tools/eval/fixture-points.json`：9 题配套题集（8 道可答 + 1 道无答案），每题带页码与原文事实；
- `tools/tests/test_fixture_eval.py`（7 例）：语料能被读取为 5 页、每个 `expect_pages` 存在、
  每个 `expect_terms` **真的出现在那一页**、无答案题的词真的不在语料里、题集 id 唯一、
  重新生成的结果与提交的一致。**题目和语料不会悄悄脱节**。

**它验证什么、不验证什么**：验证"评测链路（入库 → 检索 → Hit@k / 拒答统计）在新环境能跑通"；
不承诺某个固定数字——数字取决于用哪个向量模型（通义 / 本地 mpnet），题集注释里已写明。
真实语料上的指标仍用 `--corpus "你的文件"` 复现。

> 附带修掉两处过期数字：README 的"88 个用例"（实测 225）、`abstain.py` 覆盖率 100%（加了
> 三个函数后一度掉到 96%，补了 4 个边界用例后回到 100%；`routing.py`/`selector.py`/
> `file_profile.py` 均 100%）。

---

## 十、逐条核对表（改简历前自查）

- [x] 上述改动均已在本机实测通过
- [x] 修复前后的行为差异有可复现的对比证据
- [x] 新增测试已通过（当前 **399 passed**，其中 API 契约 57 例；前端 `npm test` **43 passed**，
      见 README「测试」一节；§3.8/§7.2 里的 88/225 是当时的口径，后续用例一直在增加）
- [x] 评测在干净 clone 上可跑通：仓库自带 5 页虚构语料 + 9 题配套题集，一致性有单测（§9.8）
- [x] 扫描版 PDF 已能检索到正文（同一份文件 209 → 2322 字符），答案带 `[第 N 页]` 引用
- [x] 汉化后已复跑端到端问答，功能无回归，且回答与引用栏均为中文
- [x] 本地化只改显示属性，后端用于匹配的值经逐条核对未变
- [x] 译文由外部服务生成并缓存（336 条），源码中**不含任何翻译词表**
- [x] 所有改动都保留了上游原有行为作为回退路径（`get_selected_ids` 的 `user_id` 为可选参数；
      `KH_UI_LANGUAGE=en` 可还原英文界面；缓存里没有的字符串一律原样返回）
- [x] 新增依赖仅 1 个（`deep-translator`），且仅用于构建词条缓存
- [ ] 尚未向上游提交 PR（可作为后续动作）
- [x] `libs/ktem/ktem_tests`、`tools/tests` 与前端测试已纳入 GitHub Actions（`.github/workflows/tests.yaml`）
- [x] 运行时提示（`gr.Info` / `gr.Warning` / `gr.Error`）已通过 3 个入口钩子纳入本地化
- [ ] `tokens` / `date_created` 两个表头仍为英文（模型判为标识符），可人工补词条
- [x] 词条缓存已提交进仓库（336 条），新 clone 开箱即中文（§9.7）
- [x] README.md 已写好（定位 / 架构 / 亮点 / 指标 / 快速开始）
- [x] 检索评测已建立并记录基线（27 题：Hit@1 59.3% / Hit@3 74.1% / MRR 0.702，§9.3）
- [x] 向量模型已按评测评选定版（mpnet-base-v2：Hit@1 36.7% → 60.0%，30 题口径，§9.4）
- [x] 评测集与文档中的语料文件名、机构信息已脱敏（`--corpus` 可覆盖）
- [x] 补齐 E5 系列需要的 `query_prefix` / `passage_prefix`（§9.4）
- [x] 补了换模型后的重建索引工具（`tools/reindex_corpus.py`，§9.6）
- [x] 向量化默认切到通义 `text-embedding-v3`（与本地 mpnet 指标相当，省 1 GB 本地模型，§9.4）
- [x] 通义走 OpenAI 兼容接口，并修掉了 embedding 不分批的问题（通义单次上限 25 条）
- [x] 仓库占用从 7.1 GB 清理到约 2.0 GB（删未用模型缓存 + 未使用的 torch，§6.3）
- [x] `.docx` 索引失败已修复：默认读取器换成纯本地的 `DocxReader`（§2.8）
- [x] 没有任何可检索文件时给出明确提示，而不是静默返回 `No evidence found.`（§2.8(f)）
- [x] 闸门认"竖排表格"（一格一行）：现场「李同学进省赛了吗」0.412 不再误拒（§5.19）
- [x] 关键词通道在全库/小选集下都能命中：`prefilter=True` 改成后置过滤（§5.19）
- [x] 关键词命中不再压过相似度匹配（27 题误拒 59.3% → 3.7%，§5.19）
- [x] 路由补回"表里有这个人"的文件：问奖学金时成绩表不再被排除在检索范围外（§5.20）
- [ ] 大表（>500 块）里的某一行仍搜不到，实体补充按体积跳过（§5.20 局限）
- [ ] 闸门仍判断不了"实体在、属性不在"（问体重/不存在的名次仍会硬答），需要答案级校验（§5.19 局限 1）
- [ ] 同一问题跨进程候选集不稳定（q27 两次评测分别含/不含 0.535 的块），根因未定位（§5.19 局限 2）
- [x] 重排已闭环：Cohere 无 key 时回退到本地词法重排，全库 Hit@3 85.2% → 88.9%（§5.9）；
      真语义 cross-encoder 仍列为后续项
- [x] 切块已从「页」改成 512/64，单文件 Hit@1 55.6% → 88.9%（§5.7）
- [x] `.pptx` 已换本地读取器；`.xls` 已换 pandas + `xlrd`；`.doc` 仍走 `unstructured`
- [x] React SPA + FastAPI `/api/v1` 已替换默认界面，`/legacy` 保留回滚（§5.25–§5.29）
- [x] `KH_APP_DATA_DIR` 可隔离演示/测试数据，截图与演示不再污染真实索引（本次）
- [ ] OCR 只处理「整页文字层不足」的情形；混排页面（部分正文是图）仍可能漏内容。

### 5.13 按文件补齐召回（"有时候问问题都没匹配到正确的文档"）

**现象**：问「李同学的社会实践完成的怎么样」（**全部搜索**），信息面板里全是
`积分细则.pdf` 的第 2、3 页，那份 `社会实践完成情况表.xlsx` 一行都没出现，最后被拒答（0.35）。

**根因（不是闸门）**：一次向量查询在**整个索引**里按相似度排序取前 10。语料里有那份
1 万块的 `.xls`（公务员简章），它的块相似度普遍 0.33–0.35；而表格行
`24405010001,李同学,8,24,2025上半年8学时` 与自然语言问题的相似度只有 ~0.34-0.41，
**挤不进 30 个候选**。也就是说：答案在库里，但不在上下文里。

**实现**（`libs/ktem/ktem/utils/retrieval.py` + `index/file/pipelines.py`）：

1. 候选扩大 `KH_RETRIEVAL_CANDIDATES`（默认 3×top_k）——给后面的名额分配留空间；
2. **缺席补查**：先看这次检索结果覆盖了哪些文件，凡是被选中的文件**一个块都没有**的，
   单独为它查一次（`KH_RETRIEVAL_MAX_FILES` 默认 8，`KH_RETRIEVAL_PER_FILE_K` 默认 3）；
   只有当"某个文件彻底缺席"时才付这次查询的代价；
3. **按文件轮转取块**：`diversify_by_source()` 让"每个文件最好的块"排在"任何文件的第二块"之前，
   避免大文件继续霸占名额；
4. **查询向量只算一次**：`VectorRetrieval.run` 新增 `query_embedding` 入参，补查时复用，
   否则每个文件都要重新 embed（实测延迟 1076 → 2400 ms 降到 1347 ms）。

**实测**（4 个文件、全库检索、同一批问题）

| 问题 | 关掉按文件补齐 | 打开 |
|---|---|---|
| 李同学的社会实践完成的怎么样 | 0.347，上下文里**没有**李同学，拒答 | **0.372，命中表格行，作答** |
| 周大鹏的学时是多少 | 0.372，只覆盖 1 个文件，拒答 | **0.409，作答** |
| 陈志强的社会实践完成了吗（表里没有） | 拒答 | 拒答（正确） |

- 上下文覆盖文件数：1–2 → **4**；
- 检索延迟：P50 **1076 → 1347 ms**（+271 ms，+25%），只发生在"确实有文件缺席"时；
- 开关：`KH_RETRIEVAL_PER_FILE`（默认开），可回退到原来的全局 top-k。

### 5.14 文件档案与按文件路由（"记住每个文件是干什么的"）

**需求**：不必每次都把全部文件检索一遍——给每个文件留一条"这个文件是干什么的"记录，
提问时先按记录挑文件，再只在挑中的文件里检索。

**档案怎么来的（不额外花钱）**：索引完成时用**已抽取的正文**生成一段确定性档案，
写进 `Source.note["summary"]`：文件名的第一/中间/最后一条摘录（各 ≤400 字，总量 ≤2000 字）。
不调模型、不联网，重建可复现。实测 4 个文件的档案（数据库里可查）：

```
文件：某班级社会实践完成情况表.xlsx
内容摘录：班级简称 学号 姓名 社会实践已修学时 社会实践待修学时 最近一次社会实践完成年份及所得学时 …
文件：公务员招考简章.xls
内容摘录：部门代码 部门名称 用人司局 机构性质 招考职位 职位属性 职位分布 职位简介 …
文件：某学院入党积极分子积分细则2025修订.pdf
内容摘录：某学院入党积极分子积分细则（2025年修订）…
```

**已有文件不需要重建**：命中检索时若发现某文件没有档案，会**当场用它的块补一份并写回**
（`_describe_files`），所以升级后第一次提问就自动补齐，第二次起直接读库。

**路由**：问答时把问题向量和档案向量比一次余弦，只留 **得分 ≥ 最高分 × 0.80** 的文件
（`KH_FILE_ROUTING_MIN_RATIO`），并至少保留 2 个（`KH_FILE_ROUTING_TOP_M` 上限 3），
低于绝对下限 0.30 则不路由（退回全量检索）。档案向量按"文件 id + 档案哈希"缓存，一个进程内每文件只 embed 一次。

**实测**（4 个文件，同一批问题）

| 问题 | 档案最相似的文件（分数） | 路由结果 | 关掉路由 | 打开路由 |
|---|---|---|---|---|
| 李同学的社会实践完成的怎么样 | 社会实践完成情况表.xlsx（0.577） | 4 → 2 | 1655 ms | 1255 ms |
| 周大鹏的学时是多少 | 社会实践完成情况表.xlsx（0.486） | 4 → 3 | 1568 ms | 658 ms |
| 奖学金怎么申请 | 励志奖学金通知.docx（0.690） | 4 → 2 | 1515 ms | 1352 ms |
| 公务员考试报名条件 | 公务员招考简章.xls（0.674） | 4 → 2 | 1711 ms | 1279 ms |

四个问题的**首选文件全部正确**；答案判定（是否拒答）与路由前一致，没有因为缩小范围而漏答。
延迟中位数约 **1568 → 1279 ms（−18%）**，文件越多收益越大（只检索 2–3 个而不是全部）。

**开关**：`KH_FILE_ROUTING`（默认开）、`TOP_M`、`MIN_RATIO`、`MIN_SIMILARITY`。
路由是纯优化：档案缺失、向量算不出来、分数不达标任一情况都退回"检索全部"，不会让问题变得答不出来。

### 5.15 中文全文索引：关键词通道一直没生效（"又出现没发现的情况"）

**现象**：路由与闸门都改好之后，问「李同学的社会实践完成得怎么样」仍然被拒答（0.38 < 0.45），
信息面板里只有那份表格的**其他几行**，李同学那一行不在上下文里。

**根因**：`LanceDBDocumentStore` 建全文索引时用的是 `tokenizer_name="en_stem"`——**按空格切词**。
中文没有空格，整句就是一个 token，于是：

- 关键词通道对任何中文问题都返回 0 条（日志里的 `Got 0 from docstore` 一直没人注意）；
- 混合检索退化成"只有向量"，而密表格行与自然语言问题的向量距离天然偏远（0.33 左右），
  永远挤不进候选；
- 名字、学号这类**精确匹配**本该由关键词通道兜住，实际全是空的。

**实现**

1. 索引改用 n-gram 分词（`base_tokenizer="ngram"`，2–3 字为一词），中文句子被切成「李同/同学/学的…」，
   问句与表格行都能匹配上；
2. 老库自动升级：`ensure_fts_index()` 首次查询时重建一次（`docstore/.fts_tokenizer` 记录分词器签名），
   10267 块重建只用 **3 秒**，不需要重建索引；
3. **关键词名额上限**：关键词命中没有相似度（分数 `-1`），一旦占满上下文，拒答闸门就"无从判断"而全部放行。
   现在 `keyword_slots = top_k // 2`，最多占一半；
4. **关键词只取必要条数**：`docstore_top_k = max(20, slots×4)`。原来取 300 条、每条都要被重排器分词，
   单次检索 3.2 秒；降到 20 条后回到 1.6 秒。

**实测**（5 个文件 / 10267 块）

| 检查 | 修复前 | 修复后 |
|---|---|---|
| `doc_store.query("李同学")` | 0 条 | **2 条**（社会实践表、综测表） |
| `doc_store.query("李同学的社会实践完成得怎么样")` | 0 条 | **3 条**（含正确的那张表） |
| 该问题的上下文 | 只有其他行 | 含李同学整行（已修 32 / 待修 0 / 2025 上 16 下 8） |
| 端到端回答 | 拒答 0.38 | **按行回答**：「已修学时 32、待修 0…」，数字与表一致 |
| "陈志强"（表里没有） | 拒答 | 仍拒答（中文提示），没有因为关键词变强而乱答 |
| 无答案集回归 | 91.7% | **91.7%** |
| 单问题检索耗时 | — | 3.2 s → **1.6 s**（取条数收敛后） |

**测试**：`libs/kotaemon/tests/test_docstore_cjk_fts.py` 5 例（中文问句命中、精确姓名命中、
分词器签名记录、老索引自动重建、空库不崩）、`ktem_tests/test_retrieval_diversity.py` 增加关键词名额 2 例。

### 5.16 "没有匹配到文件"的最后一层：选择器传了空文件列表

**现象**：问「李同学的综测情况」，回答是「知识库中没有回答这个问题所需的依据（**最佳匹配得分 0.00**）」，
而那份综测表就在文件列表里、块和向量都齐全。

**取证**：审计日志 `ktem_app_data/abstained_queries.jsonl` 记录 `best_score: 0.0`；运行日志里两行关键输出：

```
searching in doc_ids []          <-- 后端收到的文件选择是空的
Got 0 retrieved documents
```

0.00 不是"相似度很低"，而是**根本没检索**：`doc_ids` 为空，检索器直接返回 `[]`，
闸门于是用"没有依据"来回答一个它压根没查的问题。

**根因**：`get_selected_ids()` 在「在文件中搜索」模式下**原样返回下拉框的值**。上传文件会刷新文件列表
（重写 dropdown 的 choices），这一刷新会把它的 value 清空；下一次提问就带着 `[]` 进来。
空选择被当成"搜 0 个文件"，而不是"没选就搜全部"。

**实现**（`ktem/utils/selector.py` + `index/file/ui.py`）：

- 新增纯函数 `resolve_selection(mode, selected, all_file_ids)`：`all` 模式返回全部；
  `select` 模式下**空选择回退到全部**（这是刷新前用户本来的意图）；只有 `disabled` 才真的返回空；
- `get_selected_ids()` 改为先查全部文件、再交给它裁决，空选择时打印
  `file selector: search-in-file with an empty selection -> all files`——不再是无声失败。

**实测**（真实索引 5 个文件）

| 选择器状态 | 修复前 | 修复后 |
|---|---|---|
| `select` + 下拉框为空 | **0 个文件** → 拒答 0.00 | **5 个文件**（回退全部） |
| `select` + 下拉框为 None | 0 个文件 | 5 个文件 |
| `all` | 5 个文件 | 5 个文件 |
| `select` + 明确选中 1 个 | 1 个文件 | 1 个文件 |
| 「李同学的综测情况」（应用路径） | 拒答 0.00 | **按行作答**：综测 57.83 / 65.06 / 平均 61.445 |

**测试**：`ktem_tests/test_file_selector.py` 由 10 例扩到 **15 例**（全量、精确选择、空列表/None/
空字符串回退、单字符串、disabled 模式）。

### 5.17 文件档案在哪里看（§5.14 的可视化）

档案原本只存在数据库里（`index__<id>__source.note["summary"]`），要查看只能开 SQLite。现在有两个入口：

1. **「文件集合」页的表格新增 `profile` 列**（中文界面显示为「文件档案」）：一行摘录，
   下拉框/滚动即可看到每个文件被理解成什么内容；
2. **命令行 `python tools/file_profiles.py`**：逐个文件打印「块数 / 向量 / loader / tokens / 档案」，
   `--name 关键词` 过滤、`--json out.json` 出机器可读结果、`--full` 不截断；
   只读打开 `sqlite.db`，不会改动数据。档案还没生成的文件会显示「尚未生成，首次检索会自动补齐」。

实测输出（6 个文件，节选）：

```
■ 某班级学年综测汇总表.xlsx
  块数 8 / 向量 8 / loader PandasExcelReader / tokens 2340
  档案：学年：2025-2026学年 班级：某班级 汇总人：赵一鸣 … 学号 姓名 第一学期学业成绩测评 …
■ 校赛成绩发布.pdf
  块数 6 / 向量 6 / loader OCRPDFReader / tokens 1776
  档案：2026年学科竞赛校赛成绩 序号 队名 成员1（队长） 成员2 成员3 奖项 …
■ 公务员招考简章.xls
  块数 10237 / 向量 10237 / loader PandasExcelReader / tokens 6983734
  档案：部门代码 部门名称 用人司局 机构性质 招考职位 职位属性 职位分布 …
```

**实现**：`ktem/utils/file_profile.py`（纯函数：去重文件名前缀、压成单行、截断）+ 文件列表多一列；
`tools/file_profiles.py` 只读 sqlite 并渲染。测试：`ktem_tests/test_file_profile.py` 5 例、
`tools/tests/test_file_profiles.py` 6 例（含用临时 sqlite 造数据的整链验证、缺库退出码 2）。
`profile` 列头已加入中文词表（「文件档案」）。

### 5.18 表格信息被挤在一起的修复（列宽单位 + 页面宽度）

**现象**：文件集合页的表格每列都挤在一起，`profile` 列被裁、`date_created` 看不到；改成换行后
又变成**一行高得像整张表**、页面两侧还空着大片留白。

**两个根因**

1. **列宽单位**：Gradio 的 `gr.DataFrame(column_widths=[...])` 把**裸数字当像素**。原来的
   `[0, 50, 8, 7, 15, 20]` 渲染成 `0px / 50px / 8px …`，名字列只有 50px，长文本必然被裁
   （从运行实例的 `/config` 里读到的就是 `['0px', '22px', …]`）。
2. **页面宽度上限**：`main.css` 里 `#resources-tab { max-width: max(70vw, 1200px) }`，
   在 1535px 屏幕上只有 ~1074px，两侧各留 ~230px 空白——表格却在这个窄框里挤。

**实现**

1. 列宽全部改成百分比：文件表 `["0%","24%","7%","7%","12%","34%","16%"]`，
   分组表 `["0%","25%","55%","20%"]`；顺带把索引列表、模型/向量模型/重排/MCP/论文推荐/用户列表
   的裸数字列宽一并换掉（同一个坑不留一半）；
2. **`wrap=False`**：一行一个文件，行高正常；`profile` 列只放 40 字摘录，
   **完整档案在选中文件后显示在下方详情区**（标题里加「文件档案：…」）；
3. **放开页面宽度**：`#resources-tab` 的 `max-width` 改为 `max(92vw, 1400px)`，
   1535px 屏幕可用宽度从 ~1074px 提到 ~1412px（+31%）；表格高度固定 420px，多余文件滚动。

**验证**（从 7861 验证实例的 `/config` 与首页 HTML 读取，不是看代码）：

```
headers = ['id','名称','大小','tokens','加载器','文件档案','date_created']
wrap = False        widths = ['0%','24%','7%','7%','12%','34%','16%']   height = 420
首页 CSS 含 max-width: max(92vw, 1400px)
```

验证实例用完即关（7861 已释放），用户自己的 7860 未受影响。

**第二轮（按"要横向、不要纵向"+ 悬浮看全文）**

- 第一列不再是隐藏的 `id`：列顺序改为 `名称 / 大小 / tokens / 加载器 / 文件档案 / 创建时间 / id`，
  `id` 留在最后且宽度 0%（行选择仍按列名取它，不受影响）；
- 单元格改为**单行 + 省略号**（`#file_list_view td { overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap }`），不会再"溢出盖住下一列"；
- **鼠标悬浮显示全文**：`assets/js/main.js` 里加 `decorateClampedCells()`，只在
  `cell.scrollWidth > cell.clientWidth`（确实被裁）时给该格设 `title`，浏览器原生 tooltip 显示完整内容；
  Gradio 每次刷新表格会重建 DOM，所以用 `MutationObserver` 持续补挂；
- 表格高度 420px、`wrap=False`，一行一个文件，不再纵向拉长。
- 第三轮（用户反馈"id 不显示 / 不要省噪号"）：列顺序恢复为 **id 在最前**，列宽改成**按内容大致定尺的像素**
  `["250px","430px","80px","90px","150px","640px","170px"]`（合计 ~1810px，表格比容器宽时**横向滚动**），
  并去掉 `text-overflow: ellipsis`——单元格不再被画上省略号；只有真正超宽的值才会被裁，
  此时鼠标悬浮仍然给全文提示。`profile` 列取前 45 字且**不加省略号**（完整档案在下方详情区）。
  验证（重启后的实例）：`headers=['id','名称','大小','tokens','加载器','文件档案','date_created']`、
  `widths=['250px','430px','80px','90px','150px','640px','170px']`、页面不再含 `text-overflow: ellipsis`、
  含悬停逻辑与 `92vw`。
- 第四轮（用户要求去掉 id 列）：文件表不再有 `id` 列——`FILE_LIST_COLUMNS` 决定显示列，
  **行选择改为读“状态记录”**（`file_list_state`）而不是渲染出来的表格：
  `interact_file_list(records, ev)` 按行号从同一个来源取 `id`/`name`，
  `.select(inputs=[self.file_list_state])`。这样列可以自由删减而选择不受影响。
  实测（重启后实例）：`headers=['名称','大小','tokens','加载器','文件档案','date_created']`、
  `widths=['430px','80px','90px','150px','640px','170px']`、不含 `id`、不含 `text-overflow: ellipsis`、
  悬停逻辑仍在。新增 `ktem_tests/test_file_list_selection.py`（4 例：正常点选、取消选择、空列表、越界行）。
- 第五轮（两条横向滚动条）：表格里有两条同类滚动条——Gradio 的 `.table-wrap` 自己就能横向滚动，
  而组件外层（`height` 固定时）又加了一个。保留表格内那条，外层设为 `overflow-x: hidden`
  （竖向仍可滚动），并用 `#file_list_view.table-wrap` 这条更高优先级的规则兜底，
  保证无论 `elem_id` 落在外层还是滚动容器上都成立。
- 第六轮（仍有两条滚动条 → 从根源消除横向溢出）：上一轮只隐藏了外层滚动，但**表格本身仍比面板宽**。
  窗口 ~1088px 时内容区 ~1000px，而 px 列宽合计 1560px——横向溢出必然发生，于是表格自己的滚动条 +
  被撑宽的祖先 flex 容器又各给出一条。改为**按百分比分配列宽**
  `("28%","7%","7%","15%","29%","14%")`（合计 100%），表格宽度恒等于容器，横向溢出从源头消失；
  另加 `#file_list_view { min-width: 0; max-width: 100% }`，防止 flex 祖先再按内容撑宽。
  代价：超长列会被裁（**不画省略号**），全文靠悬停提示 + 下方详情区。
  验证：`widths=['28%','7%','7%','15%','29%','14%']`、合计 100、页面无 `text-overflow: ellipsis`、
  含 `min-width: 0`。
  （说明：这个沙箱里 playwright 无法拉起浏览器，本轮只能验证配置与 CSS 已生效，视觉效果由用户确认。）

### 5.19 "还是不能精确召回"：三个叠加的缺陷（2026-10-18）

**现象**：问「李同学进省赛了吗」，界面回「知识库中没有回答这个问题所需的依据（最佳匹配得分
**0.41**，低于阈值 0.45）」。但信息面板里第一块正文明明白白写着
`10 星河队 赵一鸣 钱二毛 李同学 二等奖+推荐省赛` —— 召回是对的，是**判定**错了。
审计日志（`ktem_app_data/abstained_queries.jsonl`）同时留下了这一条：
`{"question":"李同学进省赛了吗","best_score":0.412,"threshold":0.45,"reason":"low_score"}`。

用离线评测把这一题复现出来（真实 6 文件语料、不调用对话模型）：

```
python -X utf8 tools/eval_retrieval.py --eval <上面那题> --json out.json
→ top_score 0.412，名次 1（正确块就在第一名），term_evidence false，abstained true
```

顺着这条线查出**三个各自独立、又会互相掩盖**的原因：

**① 闸门的"实体证据"只认横排表格，不认竖排表格**

§5.8 的放宽要求"实体词逐字出现在**表格式行**里"（≥3 字段且 ≥60% 字段含数字）。xlsx 的行是
`24405010001 李同学 8 24 …`，满足；而这份 PDF 的读取器**一格一行**：
`10` / `星河队` / `赵一鸣` / `钱二毛` / `李同学` / `二等奖+推荐省赛`，单字段永远凑不出"字段"，
于是 0.412 ≥ 下限 0.33 也照样拒答。

**实现**（`kotaemon/abstain.py`）：新增 `line_is_a_cell(line, term)`——整行（去掉空白与
`:：,，、;；|` 之类的格内标点）**恰好等于**该实体词，即"这一行就是一个单元格"。判定改成
"表格式行 **或** 独占一行的单元格"。门槛仍然很高：散文句子永远不可能是一整行三个字。

**② 中文关键词通道在"小选集"下静默返回 0 条**

§5.15 修好了分词器（`ngram-2-3`），但 `docstore.query` 把范围过滤器写成
`where(id in (...), prefilter=True)`。Lance 这一版走的是**原生 FTS**（不是 tantivy 分支），
过滤器被下推到**命中之前**，小选集直接 0 条。实测（同一份库）：

| 同一个查询「李同学」 | `prefilter=True`（原） | `prefilter=False`（现） |
|---|---|---|
| 不传过滤器 | 3 条 | 3 条 |
| 只限定 学科竞赛 那 6 个块（答案就在里面） | **0 条** | **1 条** |
| 限定全库 10273 个块 | 4 条 | 4 条 |

也就是说：**选集越小，关键词通道越哑**——而"在文件中搜索"恰好总是小选集。端到端可见
`searching in doc_ids [...] Got 0 from docstore`：「星河队队的成员都有谁」（范围 17 块）
从 **0 条** 变成 **3 条**。

**实现**（`kotaemon/storages/docstores/lancedb.py`）：`query()` 改用 `prefilter=False`。
实测过滤器仍在**取前 N 条之前**生效（范围 7 块、全局命中 1000+ 行时仍返回该范围的全部 7 块），
不需要额外放大 `top_k`。

**③ 关键词命中排在最前，一旦通道恢复就把真正的匹配挤掉**

`VectorRetrieval.run` 原来把关键词命中**前置**（`[关键词…] + [向量…]`）。通道是 0 条时这条
无害；②一修就变成灾难：本地重排器按"问题词覆盖率"排序，关键词命中覆盖率天然高（它逐字命中），
于是被排到最前面，`diversify_by_source` 又把它当成"该文件最好的块"，真正高分块被挤出上下文。

| 27 题（积分细则集，真实 6 文件语料） | 关键事实覆盖 | 可答题误拒 |
|---|---|---|
| ②修好、命中仍前置 | **63.0%** | **59.3%**（16/27） |
| ②修好、命中改后置（现在） | 96.3% | 3.7% |
| ②未修（原状，命中近乎为 0） | 96.3% | 3.7% |

单题例子：「发明专利、软件著作权、实用新型专利怎么加分？」最高分从 **0.535** 掉到 **0.448**
（正确答案那一块被挤掉了）。

**实现**（`kotaemon/indices/vectorindex.py`）：新增 `similarity_documents_first()`，在重排之后、
截断之前把 `score < 0` 的命中排到后面——**关键词命中只补相似度排序剩下的名额，不再压过分真匹配**。

**实测（三处改动一起）**

| 集合 / 指标 | 改前 | 改后 |
|---|---|---|
| 现场三题可答题误拒（0.412 / 0.476 / 0.367） | 66.7% | **0%** |
| 「李同学进省赛了吗」 | 0.412 拒答 | **0.412 作答** |
| 「星河队队的成员都有谁」 | 0.367 拒答 | **0.367 作答** |
| 无答案集 12 题：正确拒答率 | 91.7% | **91.7%**（未放松） |
| 积分细则 27 题：关键事实覆盖 | 96.3% | **96.3%** |
| 积分细则 27 题：可答题误拒 | 3.7% | **3.7%**（两次运行 3.7% / 0%，见下） |

**测试**：`ktem_tests/test_abstain_gate.py` 20 → 27 例（竖排单元格算证据、散文仍不算、
低于 0.33 仍拒、竖排表里没有该名字不算）；`kotaemon/tests/test_docstore_cjk_fts.py` 5 → 6 例
（**限定选集**的查询必须命中——原来的用例全是不带过滤器的全库查询，所以漏了这个 bug）；
`ktem_tests/test_retrieval_diversity.py` 13 → 16 例（关键词命中必须排在所有相似度命中之后、
无命中时顺序不变、坏分数不崩）。

**局限（两个都还没修）**

1. 闸门仍只看分数 + 实体词，判断不了"实体在、属性不在"：问「李同学的体重是多少」「学科竞赛
   的省赛第一名是谁」，检索能命中同一块，闸门就放行，模型于是硬答。要解决得做答案级校验。
2. **同一个问题两次评测会拿到不同候选集**：q27 一次含第 3 页块（0.535，作答），另一次只含第 1 页
   块（0.448，拒答）。同一进程内重复查询结果一致（chroma 连查 5 次、FTS 连查 5 次都一样），
   跨进程才翻转；路由与各通道命中数两次完全相同（`6 -> 3 files`、`300 from vectorstore`、
   `20 from docstore`），根因尚未定位。这也是"有时候答得出、有时候答不出"的另一半来源。

**怎么复现**

```powershell
# 需要应用停止（共用 sqlite / LanceDB）；本题单题集合见上文的 <上面那题>
.\.venv\Scripts\python.exe -X utf8 tools\eval_retrieval.py --eval tools\eval\zh-no-answer.json
.\.venv\Scripts\python.exe -X utf8 tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json
```

> 注意：`python -X utf8` 不能省。不加时 gradio 在导入阶段用系统 GBK 读源码，
> 直接 `UnicodeDecodeError`（与 `start.bat` 里的启动方式一致）。

### 5.20 文件都在库里，为什么没被检索：路由只认"讲什么"，不认"有谁"（2026-10-18）

**现象**：问「李同学的综测可以评国家励志奖学金吗」，回答「材料中没有李同学的综合测评排名数据」。
信息面板里只有《国家励志奖学金通知》和 学科竞赛 校赛成绩——**综测汇总表明明在「文件集合」里、
块和向量都齐全**。运行日志给出了现场：

```
searching in doc_ids [6 个]
file routing: 6 -> 2 files          <-- 检索前就只剩 2 个文件
retrieval_kwargs: ...
Got 15 from vectorstore / Got 0 from docstore
```

**定位（不是闸门，也不是向量模型）**：把这道题的路由输入打出来（各文件档案 vs 问题的余弦）：

| 文件 | 档案相似度 | 是否被路由 |
|---|---|---|
| 某学院2025-2026学年国家励志奖学金通知.docx | **0.6267** | ✅ |
| 校赛成绩发布.pdf | 0.4864 | ✅（凑够"至少 2 个"） |
| 某学院入党积极分子积分细则2025修订.pdf | 0.4770 | ❌ |
| 中央机关…公务员招考简章.xls | 0.4651 | ❌ |
| **某班级学年综测汇总表.xlsx** | **0.4365** | ❌ |
| 某班级社会实践完成情况表.xlsx | 0.4318 | ❌ |

路由规则是"档案相似度 ≥ 最高分 × 0.80"（§5.14），门槛 = 0.6267 × 0.8 = **0.5014** → 只有通知达标，
再补一个 学科竞赛 凑够两个。综测表排第 5，**在查询发生之前就被排除出检索范围**，所以后面
"按文件补齐""关键词通道"都救不了它——它们只在被选中的文件里工作。

根因：**文件档案描述的是"这个文件讲什么"，回答不了"里面有没有这个人"**。成绩表在向量空间里
就是一堵数字（`24405010001 李同学 75.45 84.27 …`），永远比"奖学金通知"离问题远。

**实现**（`abstain.text_names_entity` + `routing.entity_evidence_files` / `add_entity_files`
+ `DocumentRetrievalPipeline._entity_files` / `_is_small_file`）：

1. 路由后再做一次**全库全文查询**（不嵌向量，毫秒级）：这个问题里的实体词出现在哪些块里；
2. 只认"实体词落在**表格行**或**短单元格**里"的命中（`text_names_entity`：行是表格式行，或行是
   ≤20 字且不含句读的独立单元格；名字被切成 3 字窗口，所以 `李同` 命中单元格 `李同学`）——
   散文里的同名词不算，否则"图书馆"这种主题词也会把文件拉进来（§5.8 的老坑）；
3. **补齐上限**：最多补 2 个文件（`KH_ROUTING_ENTITY_FILES`），且只补 **≤500 块**的文件
   （`KH_ROUTING_ENTITY_MAX_CHUNKS`）——1 万块的公务员简章进检索范围会把候选列表挤爆（§5.13 老坑）；
   全文候选取 30 条（`KH_ROUTING_ENTITY_CANDIDATES`）；`KH_ROUTING_ENTITY_FILES=0` 可整条关掉；
4. 与档案路由结果取并集（`add_entity_files`，去重、保序），日志会打印
   `file routing: +2 file(s) whose table names the entity (2 -> 4)`。

**实测**

| 口径 | 改前 | 改后 |
|---|---|---|
| 该题路由 | 6 → **2** 个文件 | 6 → **4** 个（补社会实践表、综测表） |
| 该题上下文 | 只有通知 + 学科竞赛 | 含 `24405010001 李同学 75.45 84.27 79.86 4 …` 的综测行 |
| 27 题关键事实覆盖 | 96.3% | **96.3%** |
| 27 题可答题误拒 | 3.7% | **3.7%** |
| 27 题检索 P50 / P95 | 434 / — ms | **405 / 975 ms**（多一次全文查询，无嵌入调用） |
| 无答案集 12 题正确拒答 | 91.7% | **91.7%** |

**中间两版被自己的实测否掉了（留档，免得再踩）**

| 版本 | 问题 | 27 题事实覆盖 |
|---|---|---|
| 只按"3 字 CJK 窗口"判实体 | `一、二、三等奖`/`加5分` 产生单字词 `分`、`二`，把公务员简章、积分细则都拉进来 | 88.9% |
| 加"≥3 字"下限、不加上限 | 公务员简章（10237 块）进了范围，q03「理论考试90分以上加几分」的上下文 10 个名额被它占 9 个 | 92.6% |
| 再加"≤500 块"体积上限 | 回到基线 | **96.3%** |

**测试**：`ktem_tests/test_file_routing.py` 13 → **21** 例（表格行/单元格/散文/长描述行/单字词不算、
按证据次数排序、不越出用户选择、并集去重与上限）。全部 65 例通过（routing + abstain + diversity）。

**局限**：实体证据是"字面出现在表格里"，不是语义判断；体积上限意味着**大表里的某一行仍然搜不到**
（1 万块的招考简章这种）；"实体在、属性不在"（问体重、问不存在的名次）仍是 §5.19 局限 1。

### 5.21 答案要跨几个文件时"不准"：路由把数据表筛掉了、行没进上下文、面板还全显示 0.0（2026-10-18）

**现象**：问「张同学能评上校级三等奖学金吗」，回答「**无法确定**……提供的材料中没有张同学的
综合测评排名、考试成绩总分排名及各科成绩信息」。信息面板里 10 个块只来自 **3 个文件**（校级奖学金
通知 ×4、国家励志奖学金通知 ×3、Mathorcup 成绩 ×3），**综测汇总表和社会实践完成情况表一块都没有**，
而这两份表的行里正好写着他的综测排名（6）、学业排名（4）、社会实践学时（32）。同时面板里**每个块都
显示 `[得分: 0.0]`、`相关性分数: 0.0`**，看不出谁排第几。

**定位一：路由 7 → 3，把两份表筛掉了**（打印档案相似度）：

| 文件 | 档案相似度 | 是否被路由 |
|---|---|---|
| 某学院关于校级奖学金评定官网通知.docx | **0.583** | ✅ |
| 某学院2025-2026学年国家励志奖学金通知.docx | 0.548 | ✅ |
| Mathorcup校赛成绩发布.pdf | 0.466 | ✅（刚好压在门槛上） |
| 某学院入党积极分子积分细则2025修订.pdf | 0.450 | ❌ |
| 中央机关…公务员招考简章.xls | 0.433 | ❌ |
| **示例班级社会实践完成情况表.xlsx** | **0.389** | ❌ |
| **示例班级学年综测汇总表.xlsx** | **0.351** | ❌ |

门槛 = 0.583 × 0.80 = **0.466**，两份表都远在门槛外——和 §5.20 是同一个根因，但这次 §5.20 的补丁
**没救回来**：实体补回返回的是 `[校级奖学金通知, Mathorcup]`，两个名额全花在**已经在检索范围里**的
文件上。原因是"实体词"取的是问题里的 3 字滑动窗口，`奖学金`(在 11/26 条全文命中里出现)、
`三等奖`(7/26)、`等奖学`(2/26) 这些**主题词**也会落进通知的表格行（`一等奖学金:综合测评在班上前
5名以内…`）和 Mathorcup 的 `三等奖` 单元格里，于是真正指向某一行的那唯一一个词（`张同学`，3/26）
没有名额了。

**定位二：就算表在范围里，行也不一定进上下文**。把路由关掉重跑，两份表确实各占 1 个名额，但
`diversify_by_source` 给的是"这个文件里向量分最高的那一块"——综测表进上下文的是
`陈晓东/赵明` 那几行（0.342），不是 `张同学 75.45 … 4` 那一行。**"这个人在哪一行"不是相似度
问题**：问题问的是"能不能评上"，和"评上"最像的是通知里的条件段落（0.488），行本身只有 0.35。

**定位三：面板全 0.0 是键名不匹配**。配置在用的是本地词法重排器，它把分数写进
`metadata["rerank_score"]`；面板读的是 `llm_trulens_score`（LLM 打分，默认关闭）和
`reranking_score`（Cohere/Voyage 的键）。三个键没对上，于是任何块都是 0.0——**检索命中与否在界面上
长得一模一样**。

**实现**

1. `abstain.row_identifier_terms`：不再按"这个词出现在多少块里"判实体，而是看**它怎么出现**
   （见下面"被实测否掉的第一版"）：
   - 一次行的标识占**单元格**：`24405010135 张同学 75.45 …` 的一个字段，或竖排表格里独占一行
     的 `张同学`；
   - 主题词是散文（`奖学金` 在句子里）或**列值**（`三等奖` 在同一个 OCR 块里重复十次）。
   于是 `张同学`(3 块) / `王丽丽`(5 块，含"汇总人"抬头) / `欧阳明月`(4 字名，只以 `欧阳明` 窗口
   出现) 都能认出来，而 `奖学金`/`三等奖` 不会。
2. `abstain.cell_names_entity`：词必须落在**单元格**里，比 §5.20 的 `text_names_entity` 严——
   那个是给路由用的"把文件放进范围"，这里判错就是**往上下文塞错块**。`一等奖学金:综合测评…`
   这行散文不算；短单元格（≤6 字的纯中文）里包含 3 字窗口算（4 字名的唯一入口）。
3. `DocumentRetrievalPipeline._entity_row_docs`：在用户**完整选择**上做一次全文查询（不是路由
   之后的子集），把"行标识落在单元格"的块挑出来，**每个文件最多 1 块、默认最多 3 块**
   （`KH_ENTITY_ROWS`）；`_promote_entity_rows` 把它们放到上下文最前，同块去重。
4. **行占独立名额**：`diversify_by_source(docs, top_k + 行数)`。第一版直接占 top_k 里的名额，
   结果「张同学在 Mathorcup 拿的二等奖能加多少入党积极分子积分」把《积分细则》的学科竞赛
   条款挤出了上下文（该题事实覆盖 100% → MISS），所以改成加名额。
5. 面板：`render.reranking_score_of`（`reranking_score` → `rerank_score`）与
   `render.relevance_score_of`（LLM 分 > 重排分 > 向量相似度；全文命中 `-1` 哨兵显示 0.0），
   标题里的 `[得分: …]` 也改用这个值。
6. 配置：`KH_ENTITY_ROWS`（默认 3，0 关闭）、`KH_ENTITY_ROW_MAX_CHUNKS`（默认 0 = 不限制
   行标识出现在多少个块里），见 `flowsettings.py`。

**实测**（同一台机器、同一语料、同一提示词；`KH_ENTITY_ROWS=0` ↔ 默认值即"改前/改后"）

| 口径 | 改前 | 改后 |
|---|---|---|
| 该题上下文 | 10 块 / 3 文件 / 4267 字符 | **13 块 / 5 文件 / 5531 字符** |
| 该题上下文是否含张同学的综测行 | ❌ | ✅（综测排名 6、学业排名 4、实践 32 学时） |
| 同一提示词 + DeepSeek 的回答 | 「**无法确定**……没有张同学的综合测评数据」 | 「综测排名约第 6、学业排名约第 4，满足前 10 / 前 15；实践完成。**具备申报资格**，名额第 6 名需参加年级评审」 |
| 跨文件 16 题关键事实覆盖 | 13/16（81.3%） | **16/16** |
| 27 题 Hit@1 / Hit@3 / Hit@5 / MRR | 96.3% / 100% / 100% / 0.975 | 96.3% / 100% / 100% / 0.975 |
| 27 题关键事实覆盖 | 100% | 100% |
| 27 题可答题误拒 | 0 题 | 0 题 |
| 无答案 12 题正确拒答 | 11/12 | 11/12 |
| 27 题检索 P50 / P95 | 589 / 2000 ms | **572 / 1654 ms**（多一次全文查询，无嵌入调用） |
| 多文件 9 题 P50 / P95 | 664 / 2646 ms | **534 / 1849 ms** |

**口径**：27 题与多文件题的 Hit@k / facts / 误拒 / 拒答，由本机只读 harness 按
`tools/eval_retrieval.py` 的同一套定义计算（应用未启动时直接构造 `DocumentRetrievalPipeline`，
读同一份 sqlite + 向量库；`KH_ENTITY_ROWS=0` 与默认值各跑一遍）。跨文件 16 题围绕本机私有语料
写成、**不随仓库提交**（含真实姓名与学号）：5 道「某人够不够条件」、6 道逐人数据、2 道跨文件
规则题、3 道单文件/对照题。回答对比用
`kotaemon.indices.qa.citation_qa.DEFAULT_QA_TEXT_PROMPT` + 默认 DeepSeek 模型，同一提示词只换检索。

**被自己实测否掉的第一版（留档）**：一开始按"这个词出现在 ≤max(3, 15%) 个全文命中块里"判实体。
实测两个方向都错——`王丽丽` 既是队员又是班级汇总人，出现在 5 个块里被当成主题词（行没进来）；
而 `三等奖` 出现在 7 个块里也算"主题词"纯属巧合。改用"单元格 + 不重复"结构判定后，
`王丽丽` 的行能补进来，`奖学金`/`三等奖` 仍被挡住。第一版还让行占 top_k 内的名额，
把另一道题的规则条款挤掉了（见实现 4）。

**测试**：新增 `ktem_tests/test_entity_rows.py` **27 例**（单元格 vs 窗口 vs 散文 vs 列值、
4 字名窗口、汇总人抬头不算、队名算、单字词不算、块数上限可选、重复次数可调、只认用户选择、
每文件一块、条数与开关、vector 模式不用全文、文档库异常不中断、提升去重）与
`ktem_tests/test_render_score.py` **6 例**（本地词法分、Cohere 分优先、LLM 分优先、
无重排时回落到向量分、全文 `-1` 不显示负分、坏值不崩）；`abstain.py` 覆盖率 **100%**、
`routing.py` **100%**。全套 `pytest`（见 README「测试」）**309 passed**。

**局限**

1. 仅 `hybrid` 模式生效：vector-only 是用户明确关掉关键词通道，不该偷偷用全文索引。
2. 行标识要求"占一个单元格"，所以**跨单元格的名字**（如 `李` / `同学` 被拆成两格）和
   **超过 6 个字的长格**（`某某某某某某研究所` 这种机构名）认不出来；同一块里重复出现 3 次以上的
   名字也会被当成列值（`MAX_CELL_REPEATS=2` 可调）。
3. 行补进来只解决"这个人的数据看不到"；**任何固定名额的检索都可能在预算之外漏块**——
   16 题里现有的跨文件题都过了，但"需要的块恰好排在候选第 20 位"这种情形仍靠
   `KH_RETRIEVAL_CANDIDATES` / `num_retrieval` 兜，重排质量仍是上限。
4. 面板的「相关性分数」是"三种信号里最强的一个"，不是校准过的置信度；LLM 打分默认关闭。

### 5.22 问「代码里是什么算法」也被拒：闸门只认散文相似度（2026-10-18）

**现象**：上传 `代码.txt` 后问「代码文件夹描述了什么算法」，回答
「知识库中没有回答这个问题所需的依据（**最佳匹配得分 0.35，低于阈值 0.45**）」。
信息面板里明明有 `代码.txt` 的块，**`# 【高斯基函数（RBF）】` 那段就在里面**。

**定位**：`代码.txt` 已经正常入库（`TxtReader`，8 块，向量与全文索引都在）。把三种问法都跑一遍：

| 问法 | 最佳相似度 | 闸门 | 上下文里有代码块吗 |
|---|---|---|---|
| 代码文件夹描述了什么算法 | 0.348 | ❌ 拒答 | ✅（10 块里 5 块来自 代码.txt） |
| 代码.txt 里描述了什么算法 | 0.386 | ❌ 拒答 | ✅ |
| 这个代码用了什么算法 | 0.392 | ❌ 拒答 | ✅ |

同一份库里，问中文散文类问题时最佳相似度是 0.5–0.7；代码（英文标识符、缩进、`->`/`@`/`#`）
和中文问题在向量空间里离得远。**这是 §5.8"表格里的数字"的对偶**：内容在库里，但相似度天生低，
全局散文阈值把"问的就是这份文件"的问题也拒掉了。实体词放宽不适用——代码里没有"表格行/单元格"。

**实现**（`abstain.named_file_evidence` + `should_refuse`）：

1. 问题里出现**所命中文件的名字**（去掉扩展名、去空白与标点后比较）时，把它当作**结构性证据**，
   门槛降到 `KH_ABSTAIN_TERM_FLOOR`（0.33）——与"实体词落在表格行"同一个下限，不是另开一套。
2. 规则刻意严格：文件名主干必须**原样**出现在问题里，所以 `代码` 只对应 `代码.txt`；
   `某学院关于校级奖学金评定官网通知.docx` 这种长名字永远不会被问题意外命中。
   主干少于 2 个字符（`a.txt`）不参与。
3. 只有**本次检索到的**文件才能作证（没被召回的文件谈不上"帮你回答"）；且最佳相似度仍须
   ≥ 0.33，0.30 这种更弱的不放行。
4. 评测工具同步，保持"衡量的是 App 的同一个决定"：`tools/eval_retrieval.py` 的结果里多一个
   `file_evidence` 字段，阈值扫描（`abstain_summary`）也认它。

**实测**

| 口径 | 改前 | 改后 |
|---|---|---|
| 「代码文件夹描述了什么算法」 | 拒答（0.348 < 0.45） | **作答**，引用 `线性基函数模型` / `高斯基函数（RBF）` / `Sigmoid` / `傅立叶` + 正则化对比 |
| 「代码.txt 里描述了什么算法」 | 拒答（0.386） | **作答** |
| 「这个代码用了什么算法」 | 拒答（0.392） | **作答** |
| 27 题（当前语料，含代码文件） | — | 关键事实 **26–27/27**、可答题误拒 **0–1**（详见下） |
| 无答案 12 题正确拒答 | 11/12 | 11/12（n12「教务处的电话」0.532 一直如此，属 §5.19 局限） |

回答对比用同一提示词 + 默认 DeepSeek 模型，只换闸门：改后答案是
"**线性基函数模型（Linear Basis Function Model）**，基函数含多项式/高斯(RBF)/Sigmoid/傅立叶，
并用不同 `Lambda` 对比正则化效果"——全部来自 `代码.txt`。

**测量口径的副作用（顺手修的两处）**：同一道题在不同进程里测出 0.448 / 0.535 两个结果
（27 题事实覆盖因此在 26/27 与 27/27 之间跳动）。已把两处**顺序不定**固定住：
`chunk_ids` 查询加 `ORDER BY id`、`rank_files` 同分按 file id 排序、评测工具的选文件列表按名字排序。
剩余抖动来自近似向量索引本身，不在本次改动范围；因此本节的 27 题数字写成**区间**而不是单值。

**局限**

1. 文件名不含问题里的词时（`main.py` + 问「这段代码」）不覆盖；这时只能靠向量相似度或
   `KH_ABSTAIN_SCORE_THRESHOLD` 下调。
2. 文件名主干是通用词（`通知.docx`、`报告.docx`）时，问「通知里写了什么」会被降到 0.33 作答，
   由 0.33 下限兜底；想更严格可把 `KH_ABSTAIN_TERM_FLOOR` 调回 0.45。
3. 这是启发式（字面命中文件名），不是语义判断；"用户问的确实是这份文件"由文件名替我们确认。

**测试**：`test_abstain_gate.py` +6 例（命名文件作答、长名字不误命中、未召回的不能作证、
过短主干忽略、0.30 仍拒、`abstain_events` 集成）；`tools/tests/test_eval_retrieval.py` +3 例
（命名文件不算拒答、不命名仍拒、阈值扫描认它）；`test_file_routing.py` +1 例（同分按 file id
稳定排序）。全套 `pytest`（见 README「测试」）**319 passed**。

### 5.23 相关文件和不相关文件的"得分"差不多：面板把两种尺子混在一列里（2026-10-18）

**现象**：问「代码.txt讲了什么算法」，信息面板里 `代码.txt` 的块是 **0.35 / 0.36**，
《积分细则》的块是 **0.29 / 0.31 / 0.36** —— 相关与不相关落在同一区间，甚至有一块不相关的
0.36 更高；顺序也是交错的（0.29 → 0.35 → 0.31 → 0.31 → 0.35 …），不是按分数排的。

**定位一：显示的是两种分数**。配置在用的是本地词法重排器，它比的是**中文字符 bigram**；
代码内容是英文标识符，所以这一题的重排分**全是 0**。面板的 `relevance_score_of` 在重排分 ≤ 0 时
**回落到向量相似度**，于是：

- 重排器**判 0** 的《积分细则》块 → 显示向量分 **0.31**；
- 重排器**认的** `代码.txt` 块 → 显示重排分 **0.29**。

两种尺子摆在一列里，数值不可比——这正是"相关和不相关得分差不多"的直接原因。

**定位二：面板顺序来自 `set` 迭代**。`citation_qa.prepare_citations` 里未被引用的块按
`llm_trulens_score` 排序，而这个分**默认关闭、恒为 0**，排序成了空操作，顺序退化成
`set` 的迭代顺序 → 相关/不相关交错、分数上下跳。

**实现**

1. `local_lexical.scoring_text`：重排时把**文件名**计入评分文本。问「代码.txt讲了什么算法」时，
   `代码.txt` 的每一块都命中 `代码`/`txt`，其他文件不命中——这就是 §5.22 用来判"用户点到了这份
   文件"的同一个结构信号，只是这里用在**排序**上。
2. `render.relevance_score_of`：**重排器跑过就用它的分（包括 0.0），没跑过才用向量相似度**
   （`has_rerank_score`）。0.0 的含义是"重排器认为没有词面重叠"，不是"没有分数"；向量分仍在
   明细里显示（`Vectorstore score:`）。
3. `citation_qa.prepare_citations`：未引用的块**按面板显示的那个分排序**（降序，doc id 打破平局），
   不再是 `set` 顺序。

**实测**（同一份库；`代码.txt` 见下面"注意"）

| 口径 | 改前 | 改后 |
|---|---|---|
| 面板里的相关/不相关块（同一题） | 相关 0.35–0.36 vs 不相关 0.29–0.36（重叠） | 相关 0.29 / 0.12 vs 不相关 **0.00**（分开） |
| 面板顺序 | 交错、按 set 顺序 | 按分数降序、两次运行一致 |
| 27 题关键事实 | 26–27/27 | 26–27/27（±1 题的波动是近似向量索引的，见 §5.22 口径） |
| 27 题可答题误拒 | 0 | 0 |
| 跨文件 16 题关键事实 | 16/16 | 16/16 |
| 无答案 12 题正确拒答 | 11/12 | 11/12 |

**注意（这次没能端到端复测代码题）**：写这节时 `代码.txt` 已不在索引里（库里只剩 7 个文件），
所以代码文件上的效果是用**单测**钉住的（`test_the_file_name_counts_as_overlap` 等），重新上传后
可以直接在界面上验证。

**局限**

1. 词法重排仍只看字面：语义相同但用词不同的块会得 0 分（面板显示 0.0，明细里还能看到向量分）。
   真正的语义重排需要 cross-encoder / LLM 重排（成本见 §5.10）。
2. 文件名计入评分意味着"文件名与问题用词相同"会被加权；文件名很泛（`数据.xlsx`）时这个信号会
   变弱甚至变噪。
3. 27 题在不同进程间仍有 ±1 题波动（近似向量索引），与本次改动无关。

**测试**：`test_render_score.py` +1 例（重排 0.0 不再回落到向量分）、`test_local_reranker.py`
+2 例（文件名计入评分、单独文件名救不了无关文件）。全套 `pytest`（见 README「测试」）**322 passed**。

### 5.24 界面视觉重构：从「Gradio 默认皮」到一套可校验的设计令牌（2026-10-18）

**背景**：反馈是「前端界面太粗糙」。逐项定位后，粗糙感来自四层叠加，而不是单一配色问题：

| 问题 | 证据（改前） | 影响 |
|---|---|---|
| 三栏比例 1:6:4，信息面板比侧栏还宽 | `pages/chat/__init__.py` 的 `scale=1/6/4`、`INFO_PANEL_SCALES={True:8,False:4}` | 聊天主区被挤窄，界面重心错位 |
| 面板无分隔（`panel_border_width=0`、`block_shadow=none`） | `assets/theme.py` | 三块区域"糊"在一起，没有层次 |
| 浅色输入框 `neutral_200` 压在 `neutral_50` 背景上 | `assets/theme.py` 的 `input_background_fill` | 灰上灰，输入区显脏 |
| 主按钮是 emerald→blue 渐变 | `assets/theme.py` 的 `gradient*` | 2023 年观感，且渐变无法做对比度校验 |
| 圆体 Quicksand 作正文，中文全部回退 | `assets/theme.py`、`main.css` 的 markmap 字体 | 中文界面字形不统一，且依赖外网字体 |
| 版本号、深色切换、展开按钮三处 fixed/absolute | `assets/js/main.js`、`main.css`（`right:-10px`） | 右上角互相叠压，像临时拼的 |
| 硬编码颜色：`mark #10b981`、图标 `#cecece`、开关 `#12df9a`、弹窗 `#fefefe` | `assets/css/main.css` | 暗色下刺眼/白底闪，无法统一调整 |
| 图标集实心/描边混用、三种颜色、非法单位 | `assets/icons/*.svg` | 侧栏按钮不成套 |
| 图标目录按 CWD 猜路径 | `pages/chat/control.py` 的 `ASSETS_DIR` | 非仓库根目录启动时图标失效 |
| 登录页标题英文（改名后词表失配） | `pages/login.py` 拼 `# Welcome to citeask!`，词表只有 `Kotaemon` 版 | 中文界面首屏就是英文标题 |
| 信息面板空状态是裸 `<h5>` | `control.py`、`reasoning/simple.py` | 未提问时一块空白 |
| 无 `:focus-visible`、无 `prefers-reduced-motion`、无媒体查询 | `assets/css/main.css` 全文 | 键盘不可见、动效不尊重系统设置、窄屏无适配 |

**设计方向**：用 `ui-ux-pro-max` 的 `--design-system` 查询
`knowledge base document QA research assistant productivity tool`（density 7 / motion 3 /
variance 3），结论是 **Minimalism & Swiss**、中性灰 + 链接蓝。落地取舍：

- 配色直接对齐 Tailwind slate/blue（Gradio 内置 `colors.slate` / `colors.blue`），
  强调色 `#2563EB`，危险 `#DC2626`，画布 `#F8FAFC` / 暗色 `#0A0F1E`。
- 字体改为系统无衬线栈 + CJK 家族（`PingFang SC` / `Microsoft YaHei` / `Noto Sans CJK SC`
  / `Source Han Sans SC`），**移除 GoogleFont**：中文界面不再依赖外网字体，也不会中英混排跳字形。
- 8px 网格；动效 120ms/180ms，`prefers-reduced-motion` 下归零。

**实现**（按层）

1. **令牌层**：新建 `assets/css/tokens.css`（66 个 `--ui-*`，浅色 `:root` / 深色 `html.dark`，
   后者比 Gradio 的 `.dark` 高一级特异性）；`assets/theme.py` 重写（Soft 基类保留、
   blue/slate、主按钮实色、系统+CJK 字体栈）；`assets/__init__.py` 新增 `load_css()`
   （tokens→main 顺序拼接）与 `read_js()`；`assets/css/main.css` 重写 1646 行、11 段
   （base→shell→workspace→sidebar→chat→evidence→tables/forms→chips/toast/modal→
   responsive→a11y→Python 工具类），**0 个十六进制色值**。
2. **应用外壳**：`main.py` 新增 `app-shell`/`app-header`/`app-brand`/`app-version`/
   `app-header-actions`/`app-tabs`；深色切换按钮从 `pages/chat/control.py` 迁到顶栏
   （全站唯一 `#toggle-dark-button`）；版本号改为服务端渲染 chip，删除 `main.js` 里
   固定定位的版本节点。
3. **工作区**：三栏改 **2:7:3**，`INFO_PANEL_SCALES={True:5,False:3}`；`#chat-workspace`
   用边框分区、`gap:0`；窄屏 <1024 信息面板落到聊天下方、<820 侧栏堆到最上、<640 单列。
4. **证据面板**：summary 内改为 `.meta` + `.chip > .chip-label/.chip-value`；
   空状态改为 `.empty-state > .empty-state-title/.empty-state-hint`（替换三处裸 `<h5>`）。
   **`<details class='evidence'>` 与 `.evidence-content` 结构逐字保留**——`main.js`
   的全文检索依赖 `#html-info-panel > div:last-child > div > details.evidence
   div.evidence-content` 这条选择器。
5. **文件页/设置/帮助/登录**：文件页加 `#index-upload`/`#file-toolbar`/`#file-selection`/
   `#chunk-panel`/`#upload-progress`；设置页每个 Tab 内容包 `.panel-card`、保存条 sticky；
   登录页改居中卡片，标题走 `tr("# Welcome to {}!").format(app_name)`（修掉改名后的
   英文标题），表单首屏即 `visible=True`（消除异步翻转造成的空白）。
6. **图标**：6 个 SVG 统一为 24×24、`fill="none"`、`stroke="#64748B"`、`stroke-width="1.75"`，
   新增 `theme.svg`；`ASSETS_DIR` 改为基于 `Path(__file__)` 的绝对路径。
7. **交互与可访问性**：新建 `assets/js/theme_init.js`（`<head>` 内、首绘前按
   `localStorage["ktem-theme"]` 或系统偏好给 `<html>` 定主题并写暗色背景防白闪）；
   `main.js` 保持单一 `function run()`（Gradio 会包成函数表达式），全程空值保护 +
   try/catch，`aria-label`/`title`/`aria-pressed` 走 `__KTEM_t` 并有 MutationObserver 补挂；
   `toggleChatColumn` 改用 `.is-collapsed` 类 + 内联 flexGrow 兜底，全局函数名不变。
8. **词表**：`assets/i18n/zh.json` +12 条（340→352），只增不删。

**实测**

| 项目 | 结果 |
|---|---|
| 对比度（解析 `_get_theme_css()`，正文/次要/链接/主按钮） | 浅色 14.63 / 7.58 / 5.17 / 4.94；深色 16.30 / 12.02 / 9.90 / 7.51 |
| 主题 CSS | 无 `gradient`、无 `googleapis`，字体栈含 4 个 CJK 家族 |
| `load_css()` | tokens 在 main 之前；main.css 十六进制 0 命中；60 个引用令牌全部有定义 |
| 新增单测 | `libs/ktem/ktem_tests/test_ui_theme.py` **14 passed** |
| 基线回归（4 文件） | **41 passed / 19 errors**，与改动前完全一致（19 个是沙箱 `tmp_path` ACL 的既有 setup error） |
| 启动日志 | `UI language 'zh': 296 labels localized, 352 catalog entries, 19 missing`（改前 295/340/20） |
| `/config` | `theme=citeask`；469 components / 252 dependencies；契约内 54 个 `elem_id` 全部命中（`app-version` 在品牌 HTML 内） |
| 首页 | `200`、610002 字节，含 `--ui-bg:`/`--ui-accent`/`ktem-theme`/`details.evidence` |

**已知限制**

1. 本沙箱无法截图（headless Chrome 启动无输出、repo 既知 playwright 不可用），
   最终观感与 1440/1024/820 三档响应式需人工目视；自动化只覆盖静态断言与 `/config`。
2. CDN 依赖未动（`pdfjs-viewer-element` / `tribute` / `markmap` / `minisearch`）。
3. `theme_init.js` 在 0/150/600/1500ms 重断言主题；若 Gradio 在此之后再次按系统偏好改写
   `<body>` 的 `dark`，极端情况下仍可能闪回一帧。
4. Gradio 4.39 的 `color_accent` 没有 `_dark` 变体，暗色强调色由 tokens 层
   （`--ui-accent` 等）承担，Gradio 自有组件里少数仍用 `primary-600`。
5. `toggleChatColumn` 依赖 `.is-collapsed` 与 Gradio 内联 `flex-grow` 的兼容，属于对
   上游实现的让步；若未来升级 Gradio 需重测。

### 5.25 第二代前端：React SPA + FastAPI（2026-10-18）

**背景与决策反转**：§5.24 在 Gradio 内部把视觉做到了上限，但反馈仍然是"界面太粗糙"。
根因不是配色，而是**渲染层被 Gradio 的组件模型锁死**：每个控件都是独立带边框的盒子，
布局只能靠 `elem_id` 补丁，无法做出"可拖拽三栏 / 抽屉 / 命令面板"这类结构。
因此推翻 [ROADMAP §7](ROADMAP.md#7-d-组明确不做) 里"重写前端：明确不做"的判断，
改为**渲染层整体替换**：Python 侧新增一层 HTTP/SSE API，Gradio 退居 `/legacy`。

**托管与回滚**（[app.py](app.py)）

```
/                React SPA（web/dist，committed）
/api/v1/*        JSON + SSE（ktem/api → ktem/services）
/legacy/         经典 Gradio 界面（gr.mount_gradio_app）
```

- `KH_WEB_UI=0` 时根路径回到 Gradio（已实测：`/` 610KB Gradio HTML，`health.ui=classic`）。
- `app.py` 用 `uvicorn` 启动；端口仍读 `GRADIO_SERVER_PORT`（默认 7860），
  `start.bat` / `scripts/bootstrap_windows.ps1` 不需要改。
- `web/dist` 的位置由 `ktem.web.resolve_web_dist` 决定：`KH_WEB_DIST` → 仓库
  `web/dist` → 包内 `ktem/web/dist`。

**后端**（`ktem/services/*` + `ktem/api/*`，均不 import gradio）

| 模块 | 作用 |
|---|---|
| `services/auth.py` | sha256 校验 + HMAC 签名的 `ktem_session` Cookie（HttpOnly/SameSite=Lax，7 天）；密钥取 `KH_SESSION_SECRET`，缺省生成 `ktem_app_data/session.key` |
| `services/conversations.py` | 会话 CRUD、`data_source` 读写、公开会话可见性、反馈；继续写旧格式 `[[user, bot], ...]`，额外写 `evidence_history` / `selected_web` |
| `services/chat.py` | 从设置/覆盖项/检索范围构建管线，`pipeline.stream` → 事件；落库、自动命名、追问建议 |
| `services/settings.py` | 扁平设置读写 + 表单 schema（`SettingItem` 驱动，label 走 `tr()`） |
| `services/files.py` | 文件列表/上传 SSE/块预览/删除/下载/分组（M2） |
| `api/*` | `auth/meta/conversations/chat/settings/files` 路由，统一前缀 `/api/v1` |

SSE 事件：`start`（可带 `warning`）→ `token`/`reset` → `evidence`（结构化数组）→
`mindmap` / `plot` → `done{message_id,name}` → `title` → `suggestions`；管线异常发 `error`
且不落库。同步管线跑在线程里，经 `asyncio.Queue` 桥接，15s 心跳；客户端断开后停止消费。

**结构化证据**（[schema.py](libs/kotaemon/kotaemon/base/schema.py)、[simple.py](libs/ktem/ktem/reasoning/simple.py)）

- `Document.channel` 增加 `evidence` / `mindmap`（向后兼容；经典页面忽略未知 channel）。
- `FullQAPipeline.structured_evidence()` 用 `match_evidence_with_context` 的 spans 生成
  `{id,file_id,file_name,page,type,score,vector_score,rerank_score,llm_score,text,file_path,cited,spans}`，
  按"被引用优先、再按面板分数"排序；**拒答分支也会发证据**（本轮实测 10 条），
  经典 HTML 面板继续保留（同一份 `docs`、同一套打分函数）。

**前端**（[web/](web)）

- 栈：React 18 + TypeScript 5.6 + Vite 5 + Tailwind 3.4 + Radix/shadcn 手写基元 +
  react-query + zustand + react-markdown/highlight + cmdk + resizable-panels。
- 已实现：`/login`、`/chat`、`/chat/:id`；Rail + 可拖会话侧栏（搜索/分组/hover 操作）、
  空状态建议问题、流式回答（骨架/光标/markdown/代码高亮/停止/重试/复制/反馈）、
  证据抽屉（搜索/相关性条/被引用标记/打开原文/`【n】` 联动）、聊天设置弹层、
  `⌘/Ctrl+K` 命令面板、明暗主题（首绘前防白闪）、中英文案、1024/1280/820 响应式。
- M2：`/files`（搜索 + 原生上传/URL（SSE 进度）+ 文件表与行操作（查看分块/下载/重建索引/删除）
  + 分组 CRUD + 分块抽屉）与 `/settings`（schema 驱动表单、左分组导航、吸底保存/放弃、
  未保存提示、数字内联校验）已替换占位页。
- `/resources` `/help` 仍为"经典界面"卡片 + `/legacy` 链接（M3）。

**实测**

| 项目 | 结果 |
|---|---|
| 后端新增测试 | `test_api_auth_meta` 6 + `test_api_conversations` 4 + `test_api_chat` 3 + `test_evidence_channel` 3 + `test_api_files` 17 + `test_web_host` 4 = **37 passed** |
| 前端 | `npm test` **41 passed**；`npm run lint` 0 警告；`npm run typecheck` 通过 |
| 构建 | JS 887.80 kB → **gzip 264.60 kB**（预算 350）；CSS 44.02 kB / 9.65 gzip；`node --check` 通过 |
| 真实链路 | DeepSeek 回答 **328 个 `token` 事件**、`evidence` 9 条、自动标题、`done` 落库；拒答分支 `start/evidence/token/done` 齐全 |
| 托管 | `/` 200 且引用哈希资源；`/assets/*.js|css` 200；`/api/v1/health` 200；`/legacy/` 200（Gradio 626KB） |
| 回滚 | `KH_WEB_UI=0`：`/` 回到 Gradio，`ui=classic` |
| 经典界面回归 | 既有测试基线不变：4 个 i18n/render/file-list 文件 **41 passed / 19 errors**（19 个是沙箱 `tmp_path` ACL 的既有环境错误） |

**已知限制 / 后续**

1. 观感与响应式已用 agent-browser 在 1440×900 逐页截图复核（登录/聊天/证据/文件/设置，明暗两套），
   但最终是否合意仍需人工目视；自动化覆盖的是构建、API、SSE 与托管契约。该浏览器需要写
   `%USERPROFILE%\.agent-browser`，本沙箱下必须提权运行，普通终端无此限制。
2. M3 的 Resources / Help / 用户管理页面尚未迁移（API 已就绪或待建）；Gradio 仍在 `/legacy`。
3. 本沙箱禁止向新建子目录写文件，**原生上传无法在本会话完成端到端验证**（`mkdtemp` 后写入即
   `Permission denied`，接口返回 403）；上传/重建索引逻辑由 `test_api_files.py` 的 17 例覆盖，
   真实上传需在普通环境点一次。列表（7 行）、分块（4 块）、设置 schema（6 组）/values（40 键）
   均已通过 7860 实测。
4. 本沙箱的 shell/Node 不能写 `libs/**`，所以构建输出落在仓库 `web/dist`；
   `libs/ktem/ktem/web/dist/` 内只是占位，发布时用
   `scripts/build_web.ps1`（普通机器）把产物复制进包内。
5. 构建链在本沙箱绕开 esbuild（`web/scripts/sandbox-shim.mjs` + Vite API + Babel + terser），
   普通终端效果相同；`npm run dev` 的依赖预打包依赖 esbuild，需在普通终端运行。
6. `messages[]` 暂无逐条时间戳，日期分隔回退到会话创建时间；如需多日期分隔，
  下一步给消息加 `created_at`。
7. PDF 预览当前复用 `/legacy/file=<path>#page=N`（浏览器内置阅读器），原生 PDF.js
  阅读器（页码跳转 + 文本高亮）尚未迁移；设置页也不处理用户密码（仍在 `/legacy`）。
8. 打包复制路径：`scripts/build_web.ps1 -CopyToPackage`（根目录脚本是 `web/scripts` 的薄封装）。
9. 首屏 JS 已到 264 kB gzip（预算 350 kB，但增长很快）；继续加页面时应先做路由级 `lazy()` 拆分。

### 5.26 登录前 `/meta` 无限 401、卡在"加载中"（2026-10-18，回到 §5.25）

**现象**（用户实测日志）：打开 `http://127.0.0.1:7860/` 后 `/api/v1/meta` 连续 401，
120 秒内 **246 次**，页面永远停在"加载中…"，登录表单根本点不到，日志里也从来没有
`POST /api/v1/auth/login`。

**根因**（用 CDP 抓到的调用栈 + 请求时序确认）：`/api/v1/meta` 需要会话（`test_api_auth_meta`
明确规定匿名 401），但 `App` 在 `user === null && metaQuery.isLoading` 时渲染启动屏，而
`LoginPage` 自己也 `useMeta()`。于是形成循环：

1. meta 401 → 查询失败 → `App` 认为"没在加载" → 渲染 `/login` → `LoginPage` 挂载；
2. `LoginPage` 的 `useMeta` 观察者挂载即触发 `refetchOnMount` → meta 重新 pending；
3. `App` 又看到 `metaQuery.isLoading` → 退回启动屏 → `LoginPage` 卸载 → 请求失败；
4. 回到第 1 步。请求栈为 `QueryObserver.onSubscribe → Query#fetch`，正好对应"挂载即取"。

雪上加霜的两点：全局默认 `retry: 1` 对 4xx 也重试；401 事件把 `me` 置空又触发一轮渲染。

**修复**

| 文件 | 改动 |
|---|---|
| [web/src/lib/retry.ts](web/src/lib/retry.ts) | 新增 `shouldRetry()`：**4xx 一律不重试**，5xx/网络错误最多再来一次 |
| [web/src/lib/query.ts](web/src/lib/query.ts) | 默认 `retry` 改为 `shouldRetry` |
| [web/src/hooks/use-api.ts](web/src/hooks/use-api.ts) | `useMeta(enabled)`：未登录不请求 `/meta` |
| [web/src/App.tsx](web/src/App.tsx) | 启动只等 `/auth/me`；已登录才等 meta；meta 失败显示"重试"错误页而不是无限转圈；401 时清掉 meta 缓存 |
| [web/src/pages/LoginPage.tsx](web/src/pages/LoginPage.tsx) | 登录页不再请求 meta（未启用用户管理时 `/auth/me` 会直接返回匿名用户并跳转） |
| [web/src/lib/api.ts](web/src/lib/api.ts) | `/api/v1/auth/*` 的 401 是"密码错"，不再广播会话失效 |

**同时修掉的观感缺陷**（截图逐页复核）：登录卡片垂直居中；证据面板默认收起、有证据才自动展开；
输入框从 40px 起步（原先被固定在 200px 上限）；页头"新对话"只在侧栏收起或窄屏出现；
设置页的索引分组标题走 `tr()`（`File Collection` → `文件集合`）；文件页副标题不再重复索引名；
空状态在可视区垂直居中。

**验证**

| 项目 | 结果 |
|---|---|
| 匿名打开 `/` | 只有 1 个 `GET /api/v1/auth/me` 200，**0 个 meta 请求**，登录表单立即可用 |
| 登录 | `POST /auth/login` 200 → `meta` **只请求一次** 200 → `/conversations` 200 |
| 真实问答 | 问题"国家励志奖学金的申请条件是什么？" → 结构化回答、证据面板自动打开 **9 条证据**、自动标题 |
| 前端 | `npm test` **41 passed**（新增 `retry.test.ts` 3 例）、typecheck / lint 通过 |
| 构建 | JS 887.80 kB → gzip **264.60 kB**（+0.41 kB） |
| 浏览器 | agent-browser 1440×900 截了登录/空态/问答/证据/文件/设置/暗色共 11 张逐页检查 |

日志开头那两行 `ALTS creds ignored ... untrusted ALTS is not enabled` 是 gRPC/absl 在
非 GCP 环境初始化时的固定噪音（`E0000` 只是被当成 error 打出来），与前端无关，可忽略。

### 5.27 对话视图补齐：思维导图持久化、证据对齐、窄屏浮层（2026-10-19，承接 §5.25/§5.26）

**问题 1：刷新后证据全没了（真 bug）**

服务端把 `evidence_history` 存成**每个问答对一条**，而消息列表按**消息**索引（答案在奇数位）。
实时流里前端把证据写在 `assistantIndex`（如 1），与载入时的 `evidence_history[1]`（只有 0 号元素）
对不上，于是重开历史会话时证据面板为 0 条、每条消息下的"N 条证据"也不显示。

修复（[use-chat-stream.ts](web/src/hooks/use-chat-stream.ts)）：新增 `toMessageIndexed()`
（载入时把按对的数组按 `2i+1` 铺到消息索引）与 `toPairIndexed()`（写回 react-query 缓存时压回
服务端形状），实测刷新后仍显示 **9 条证据**。

**问题 2：思维导图在网页端被丢弃**

`onMindmap: () => undefined` —— 后端 `mindmap` 通道发出来了、也落库了，前端却什么都不做。
现在：

- 后端：[conversations.py](libs/ktem/ktem/services/conversations.py) 的 `persist_turn(..., mindmap=...)`
  把 markdown 写进 `mindmap_history`（按对对齐，`regenerate` 覆盖最后一条而不是追加），
  `GET /conversations/{id}` 一并返回；[chat.py](libs/ktem/ktem/services/chat.py) 在收到
  `channel == "mindmap"` 时记住文本并透传。
- 前端：答案下方出现可折叠的「思维导图」卡片（原生 `<details>`，默认收起），内容按 markdown
  渲染，与答案、证据一起随会话持久化。

**问题 3：窄屏首屏被抽屉/浮层盖住**

宽度 < 1024px 时会话列表和证据面板都是浮层，而它们的显示状态来自持久化偏好（常常是 true），
一进页面就整块盖住聊天内容。现在窄屏挂载时自动收起二者，且证据**只在宽屏**随首个证据自动展开
（窄屏留给顶栏按钮，避免遮住答案）。

**验证**

| 项目 | 结果 |
|---|---|
| 后端 | 新增 `test_mindmap_is_stored_next_to_its_answer`（写入 + 重生成覆盖），API 套件 **38 passed** |
| 前端 | `npm test` **41 passed**、typecheck / lint 通过；JS gzip **265.11 kB** |
| 真实链路 | `USE_LOW_LLM_REQUESTS=false` 启动 → 提问后生成思维导图 markdown（`mindmap_history` 实测有内容）、刷新后卡片与 9 条证据都还在 |
| 窄屏 | 820×900 实测：无会话抽屉、无证据浮层，顶栏出现「新对话」 |
| 宽屏 | 1440×900 实测：思维导图折叠卡 + 停靠证据栏 + 每条消息的证据计数 |

**环境提示（不是代码问题）**：本机访问不到 `huggingface.co` 时，`App()` 会为
`mistralai/Mixtral-8x7B-v0.1` 的 tokenizer 重试 HEAD 约 90 秒才继续启动；设
`HF_HUB_OFFLINE=1`（配 `TRANSFORMERS_OFFLINE=1`）即可跳过。测试时另加
`-p no:cacheprovider`，否则 pytest 收尾写 `.pytest_cache` 的 `mkdtemp` 在受限沙箱里会卡住。
`.env` 里 `USE_LOW_LLM_REQUESTS=true` 时 `meta.features.mindmap` 为 false，聊天设置里不显示
思维导图开关（既有语义：低 LLM 调用模式不生成 mindmap），需要时把它设为 false 再重启。

### 5.28 M3：资源、帮助与账户页面（2026-10-19）

侧边栏里原本还是「请去经典界面」占位卡的两页，以及账户改密，都换成了真页面。

**后端（新增 3 个路由模块 + 1 个服务）**

| 文件 | 内容 |
|---|---|
| [services/users.py](libs/ktem/ktem/services/users.py) | 用户 CRUD 与改密；规则与经典页一致（用户名 3–32 位字母数字下划线、大小写不敏感；密码 ≥8 位且含大小写/数字/特殊字符）；删除自己、降级自己、删掉最后一个管理员都会被拒 |
| [api/users.py](libs/ktem/ktem/api/users.py) | `GET/POST /users`、`PATCH/DELETE /users/{id}`，全部 `admin_required`（非管理员 403） |
| [api/auth.py](libs/ktem/ktem/api/auth.py) | 新增 `POST /auth/password`：校验当前密码后改自己的密码 |
| [api/resources.py](libs/ktem/ktem/api/resources.py) | `GET /resources`：索引（id/名称/私有/文件数）+ LLM/向量/重排/MCP 的**只读**清单 |
| [api/help.py](libs/ktem/ktem/api/help.py) | `GET /help`：随包的 `docs/about[.zh].md` 与 `docs/usage[.zh].md`、版本号与界面语言 |

资源清单只暴露 `name / vendor(类名) / model / default`，**不返回 spec**（里面有 API key），
测试里直接断言响应文本不含 `api_key`。

**前端**

- [ResourcesPage.tsx](web/src/pages/ResourcesPage.tsx)：三个 tab——索引集合（表格 + 查看文件）、
  模型资源（LLM/向量/重排/MCP 四组，默认项打「默认」徽标）、用户（管理员可见：新建/编辑/
  重置密码/删除，删除自己被禁用）。索引与供应商的增删改仍需经典界面并重启，页脚与顶栏都给了入口。
- [HelpPage.tsx](web/src/pages/HelpPage.tsx)：关于（版本/语言/项目主页/经典界面）+ 使用指南
  markdown + 快捷键。
- [AccountCard.tsx](web/src/components/settings/AccountCard.tsx)：设置页顶部的「账户」卡片，
  当前密码 + 新密码 + 确认，前端只校验两次一致，其余规则交给后端。
- 路由替换后 [ClassicPage.tsx](web/src/pages/ClassicPage.tsx) 与 [PageShell.tsx](web/src/components/app/PageShell.tsx)
  不再被引用，已删除；`classic.*` 只保留仍被文件页使用的 `classic.open`。

**验证**

| 项目 | 结果 |
|---|---|
| 后端 | 新增 `test_api_users.py` 7 例（列表不带密文、创建后可登录、校验、重命名/重置、自己不可删/降级、非管理员 403、改密流程）+ `test_api_help_resources.py` 3 例；API 套件 **48 passed** |
| 前端 | `npm test` 41 passed、typecheck / lint 通过；JS gzip **268.82 kB** |
| 浏览器 | 1440×900 与 820×900 实测：三个 tab、创建用户→列表出现→删除→toast 全链路；帮助页渲染 about/usage；设置页账户卡；暗色正常 |
| 数据 | 实测 LLM 7 条、向量 6 条、重排 1 条、MCP 0 条；索引 1 个（文件集合，7 个文件） |

**仍未迁移（M4 才是收尾）**：Gradio 的模型供应商**编辑**表单、索引的新增/删除、以及 MCP 配置
仍在 `/legacy`；这些操作要么依赖重启，要么是长表单，本轮只做只读视图 + 入口，避免做出一个
半可用的编辑器。用户管理、账户改密、帮助文档已经可以在新界面完成。

### 5.29 M4 起步：模型供应商与 MCP 的增删改（2026-10-19）

经典界面里最大的那块表单——LLM / 向量 / 重排供应商与 MCP 配置——搬到新界面。改动不是手写
一堆固定字段，而是**从供应商类自己的 `describe()` 生成表单**，所以以后新增供应商不用改前端。

**后端**

| 文件 | 内容 |
|---|---|
| [services/vendors.py](libs/ktem/ktem/services/vendors.py) | 供应商目录（`llms.vendors()` + `describe()["params"]` → 字段名/类型/帮助/必填/默认/是否密文）+ 三类模型的 CRUD + MCP CRUD；`test_llm()` 只构造客户端、**不发请求**（不花 token） |
| [api/vendors.py](libs/ktem/ktem/api/vendors.py) | `GET /vendors`（目录）、`GET /vendors/{kind}`（列表）、`GET/POST/PATCH/DELETE /vendors/{kind}[/{name}]`；读目录任意登录用户可用，**改配置与读 spec 仅管理员**（spec 里是 API key） |

细节：列表接口只回 `name/vendor/model/default`，spec 只在单条详情里给并且要求管理员；`PATCH`
合并参数而不是整份覆盖，`__type__` 保留；把某个模型设为默认时管理器会自动清掉其它默认项。

**前端**

- [VendorDialog.tsx](web/src/components/resources/VendorDialog.tsx)：按目录生成表单（必填标 `*`、
  密文用 password 框、`bool` 用开关、`int/float` 用数字框）；类型标签简化为 `str` / `str?` / `bool?`；
  「检查配置」调 `POST /vendors/llms/test`；额外参数可在「高级参数（JSON）」里补，保存时合并。
- [McpDialog.tsx](web/src/components/resources/McpDialog.tsx)：MCP 是自由 JSON（`command/args/env`
  或 `url`），直接编辑 JSON 并做解析校验。
- [ResourcesPage.tsx](web/src/pages/ResourcesPage.tsx)：模型资源四个分组都可增删改（删除有确认，
  删默认模型会额外提示回退），非管理员只读；刷新后 `meta` 一并失效，聊天页的模型下拉立即跟上。

**验证**

| 项目 | 结果 |
|---|---|
| 后端 | 新增 `test_api_vendors.py` 8 例（目录字段、LLM 全流程、默认项移动后**恢复原默认**、未知供应商/重名 400、嵌入创建删除、MCP CRUD、非管理员 403、匿名 401）；API 套件 **56 passed** |
| 前端 | `npm test` 41 passed、typecheck / lint 干净；JS gzip **271.92 kB** |
| 浏览器 | 实测：新增 `uiverify-llm`（ChatOpenAI）→ 列表出现 → 编辑改 model 为 gpt-4o → 检查配置返回「模型配置有效（未实际发送请求）」→ 删除；MCP 同理新增/删除；测试条目已清理，默认模型仍是 `deepseek` |
| 修正 | 目录按管理器注册顺序（ChatOpenAI 在前）、toast 文案区分用户/模型、MCP 按钮文案、去掉字段占位符与帮助文字重复 |

**M4 剩余**：索引的新增/删除（依赖重启，经典界面写入后用 `app.index_manager` 重建，需要单独设计
重启提示与失败回滚），以及下线 Gradio 默认入口（`KH_WEB_UI` 开关与经典页面的去留）——这两步
建议单独一轮做，避免和已验证的供应商编辑混在一起。












### 5.30 React 内联引用显示为原始 HTML（2026-10-19）

**现象**：把聊天设置里的引用策略切到「引用：内联」后，答案正文直接出现
`<a href='#' class='citation' id='mark-1'>【1】</a>`，而不是可点击的引用标记。

**根因**：上游的内联引用管线 `AnswerWithInlineCitation.replace_citation_with_link()`
把 `【n】` 替换成 HTML anchor，供经典 Gradio 页面用 CSS/JS 渲染；新的 React 端
`ReactMarkdown` 默认不解析原始 HTML（未装 `rehype-raw`），于是把 anchor 当普通文本输出。
这是"迁移到新渲染层后，旧层的输出格式没有适配"的典型问题。

**修复**（[citations.ts](web/src/lib/citations.ts) + [Markdown.tsx](web/src/components/chat/Markdown.tsx)）

- 新增 `normalizeCitationLinks()`：在 Markdown 渲染前把
  `<a ... class='citation' ...>【n】</a>` 还原成 `【n】`；普通链接与其它 class 不动。
- 渲染器已有的 `splitCitations()` 继续把 `【n】` 变成可点击的 `citation-chip`，
  证据抽屉的 `onCitation` 联动不变。

**验证**

| 项目 | 结果 |
|---|---|
| 前端单测 | 新增 2 例（anchor 还原、普通链接不受影响），`npm test` **43 passed**；typecheck / lint 干净 |
| 浏览器 | 「引用：内联」提问「英语四级和六级分别加几分？」→ 答案显示上标 `1`，证据面板显示「已被引用」、第 2 页 36% |
| 回归 | 默认「无引用」、经典 Gradio 界面与既有证据联动均不受影响 |
