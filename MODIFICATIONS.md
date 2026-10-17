# 对 kotaemon 上游项目的修改记录

> 本文档记录本仓库相对于上游 [Cinnamon/kotaemon](https://github.com/Cinnamon/kotaemon) 的**全部改动**，
> 包括每处改动的动机、定位过程与验证证据，供后续整理简历与面试叙述使用。
>
> **基线版本**：`v0.12.0`（commit `9ad3e4e`，上游 main 分支）

---

## 一、总体改动一览

### 已跟踪文件的修改（21 个文件，+395 −59 行）

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
| [libs/kotaemon/kotaemon/indices/ingests/files.py](libs/kotaemon/kotaemon/indices/ingests/files.py) | **缺陷修复** | `.pdf` 默认抽取器换成 OCR 感知版本（§2.7） |
| [libs/kotaemon/kotaemon/loaders/\_\_init\_\_.py](libs/kotaemon/kotaemon/loaders/__init__.py) | **功能新增** | 导出 `OCRPDFReader` |
| [libs/kotaemon/kotaemon/embeddings/fastembed.py](libs/kotaemon/kotaemon/embeddings/fastembed.py) | **缺陷修复** | 补 `query_prefix` / `passage_prefix`（E5 系列必需，见 §9.4） |
| [libs/kotaemon/kotaemon/embeddings/openai.py](libs/kotaemon/kotaemon/embeddings/openai.py) | **缺陷修复** | 补 `batch_size` 分批（通义单次上限 25 条，见 §9.4） |
| [.env.example](.env.example) | 工程化 | 补充通义 key、本地向量模型、语言、OCR 等配置项 |
| [libs/kotaemon/pyproject.toml](libs/kotaemon/pyproject.toml) | 依赖 | 新增 `rapidocr-onnxruntime`、Windows 下的 `python-magic-bin` |
| [flowsettings.py](flowsettings.py) | **功能集成** | DeepSeek + 本地 FastEmbed 接入；4 个语言配置项（含回答语言） |
| [libs/ktem/pyproject.toml](libs/ktem/pyproject.toml) | 依赖 | 新增 `deep-translator` |
| [.gitignore](.gitignore) | 工程化 | 忽略运行时缓存目录 |

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

> 影响范围提示：`.pptx`、`.xls`、`.doc` 仍走 `unstructured`，在同样的环境里可能遇到相同问题；
> 需要时按同样方式换成本地读取器（`DocxReader`/`PandasExcelReader` 等已在仓库内）。

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

---

## 八、简历表述建议

### 8.1 一句话版本

> 在开源 RAG 项目 kotaemon 上完成本地化改造、缺陷修复与全链路汉化：接入 DeepSeek + 本地 FastEmbed
> 实现零 embedding 调用成本的知识库问答；定位并修复了默认配置下检索被静默跳过的缺陷，
> 消除了模型脱离文档凭记忆作答的幻觉风险；并在上游无 i18n 机制的前提下，实现了一条
> 「采集 → 外部翻译服务 → 词条缓存 → 回写」的本地化流水线（译文不落源码），
> 覆盖构建期组件、运行时拼装与浏览器端三层，并让模型回答语言跟随界面语言。

### 8.2 分点版本（STAR）

- **背景**：基于开源 RAG 框架 kotaemon 搭建本地文档问答系统，要求对话走 DeepSeek API、
  向量化完全本地化以消除 embedding 调用成本。
- **改造**：上游配置层无法表达「DeepSeek 对话 + 本地 FastEmbed 向量」这一组合
  （默认 embedding 会绑定到不提供该接口的 DeepSeek），因此重构了模型注册逻辑，
  引入显式的默认项收敛机制，保证多 provider 并存时默认模型唯一且可用。
- **缺陷定位**：集成测试中发现**检索静默失效**——模型绕过文档用训练记忆作答。
  通过对比不同检索范围模式的行为，将问题收敛到前端选择器的状态解析，
  最终定位到两处叠加缺陷：选择器默认值不在可选项内导致 UI 呈未选中态；
  以及全库检索分支依赖一个仅在用户手动交互时才会刷新的陈旧状态值。
- **修复**：将默认检索范围改为全库，把会话中已有的权威用户标识透传到选择器，
  同步覆盖 File 索引与 3 个 GraphRAG 索引分支，参数保持可选以向后兼容；
  并将选择器逻辑抽为纯函数，使「默认值必须属于可选集合」这一不变量可被断言。
- **验证**：通过 Gradio HTTP API 驱动真实 UI 事件序列完成端到端验证，
  修复前/后行为可复现对比；补充 10 个回归用例（`libs/ktem/ktem_tests/`），
  并回归验证按文件检索路径未受影响。
- **界面汉化**：Gradio 4.39 无 i18n 机制，且译文不应写死在源码里，因此实现了一条
  「**采集 → 外部翻译 → 词条缓存 → 回写**」的流水线：只改写「会被渲染为文字」的属性，
  以 `(标签, 值)` 二元组翻译选项、严格保留后端用于匹配的值；译文由 `deep-translator`
  与已配置的对话模型批量生成并缓存到 JSON，共 336 条，运行时只读缓存。
  过程中发现并解决了三类真实问题：免费后端 Google 持续 429、机器翻译破坏 Markdown 结构、
  以及逐条翻译导致语言名互相污染（`English` 与 `Chinese` 都变成「中文」）。
- **运行时与浏览器端补漏**：第一版上线后仍残留英文，排查发现这些串在构建完成后才产生
  （引用块标签、事件回调提示、`version:` 等），不属于组件树。为此把词表扩展成三个消费端：
  运行时 `tr()` / 模板回填（f-string 消息正则匹配后插值）、Gradio 通知的 3 个入口钩子
  （一处改动覆盖约 50 条弹窗）、以及注入 `window.__KTEM_t` 供 JS 查表；
  并用 `ast` 做源码串提取（相当于 xgettext），使新增调用点自动进词表。
  同时把答案语言绑定到界面语言，使中文提问得到中文回答与中文引用。
- **验证**：汉化后复跑端到端问答，确认回答为中文、分数与文档一致（15/15/40 分）、
  引用栏标签全部中文；五个测试文件 **88 passed**。
- **扫描件检索**：用户上传的制度文件是扫描版 PDF，文字层只有标题，检索只能命中标题、
  模型无正文可依。通过导出索引块定位到「4 个 37–59 字符的标题块 + 4 个 `Page thumbnail` 图片块」，
  确认问题在**数据入口**而非检索算法；随后实现按页判断的 OCR 抽取器（本地 PP-OCR，
  纯文本模型看不到图片，所以必须把图片转成文字进索引），同一份文件正文从 209 字符恢复到 2322 字符，
  重建索引后模型给出的分数与原文一致并带页码引用。
- **可量化**：把「问一句看对不对」升级成**检索评测**（30 条带页码与关键事实的问题，
  只跑检索层、零 token 成本），首次跑出 Hit@1 36.7% 的基线；再用同一套评测做**向量模型选型**，
  换掉 2020 年的 MiniLM 后 Hit@1 提到 **60.0%**、MRR 0.589 → **0.739**，
  同时发现框架调用 embedding 时丢掉了 E5 系列必需的 query/passage 前缀（补上后同一模型 +6.6pp）。
  > 上述对比在题库 30 题版本上测得；发布版题库精简为 27 题（去掉了 3 道含内部文件专有信息的题），
  > 基线随之重算为 Hit@1 59.3% / MRR 0.702，两套口径不可直接相减。
- **可复现**：中文词表生成后提交进仓库（336 条），配合 `load_catalog()` 的
  「仓库词表 + 用户词表覆盖」合并策略，使**新 clone 开箱即中文**；补齐 README、评测命令
  与换模型后的重建索引工具。

### 8.3 可延伸的面试话题

| 话题 | 可讲的内容 |
|---|---|
| RAG 幻觉治理 | 为什么「检索召回为空」比「检索召回了错的内容」更危险——模型不会报错，只会自信地编 |
| 评测驱动迭代 | 为什么必须先有「只跑检索层、零成本」的评测，才能谈换向量模型、开重排、改切块——否则所有优化都是感觉 |
| 指标读法 | 语料只有 4 个块时 Hit@5 必然 100%，区分度在 Hit@1/MRR；事实覆盖率 100% 说明问题在排序而非召回 |
| 验证策略 | 为什么必须用「文档里有、公开知识里也有但答案不同」的问题来验证检索，而不是随便问一个 |
| 可测性设计 | 为什么把「默认模式」抽成常量并断言它属于可选集合，比端到端兜底更早暴露缺陷 |
| CI 盲区 | `libs/ktem/ktem_tests/` 存在但 CI 只跑 `libs/kotaemon`，属于可提改进项 |
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

---

## 十、逐条核对表（改简历前自查）

- [x] 上述改动均已在本机实测通过
- [x] 修复前后的行为差异有可复现的对比证据
- [x] 新增测试已通过（`88 passed` = 对话 14 + 选择器 10 + 本地化 44 + MCP 13 + PDF OCR 7）
- [x] 扫描版 PDF 已能检索到正文（同一份文件 209 → 2322 字符），答案带 `[第 N 页]` 引用
- [x] 汉化后已复跑端到端问答，功能无回归，且回答与引用栏均为中文
- [x] 本地化只改显示属性，后端用于匹配的值经逐条核对未变
- [x] 译文由外部服务生成并缓存（336 条），源码中**不含任何翻译词表**
- [x] 所有改动都保留了上游原有行为作为回退路径（`get_selected_ids` 的 `user_id` 为可选参数；
      `KH_UI_LANGUAGE=en` 可还原英文界面；缓存里没有的字符串一律原样返回）
- [x] 新增依赖仅 1 个（`deep-translator`），且仅用于构建词条缓存
- [ ] 尚未向上游提交 PR（可作为后续动作）
- [ ] 尚未把 `libs/ktem/ktem_tests` 纳入 CI（可作为后续动作）
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
- [ ] 用本地 ONNX cross-encoder 替换空配置的 Cohere 重排，并用同一套评测量化提升（§9.5）
- [ ] 切块粒度仍是「页」（`chunk_size=0`），细化后应能提升 Hit@1
- [ ] `.pptx` / `.xls` / `.doc` 仍走 `unstructured`（受同一 `libmagic` + 403 影响），
      需要时按 `.docx` 的方式换成本地读取器
- [ ] OCR 只处理「整页文字层不足」的情形；混排页面（部分正文是图）仍可能漏内容。
