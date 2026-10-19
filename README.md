# citeask

[![tests](https://github.com/wangwuqiang2026/citeask/actions/workflows/tests.yaml/badge.svg)](https://github.com/wangwuqiang2026/citeask/actions/workflows/tests.yaml)

文档问答系统：**扫描件与长文档可直接入索引，答案逐页可溯源，检索效果用评测驱动迭代。**

> Document QA with OCR-aware ingestion, page-level citations, and an evaluated retrieval pipeline.

面向的场景很具体：把一份**扫描版 PDF**（学校/单位的积分办法）变成可以按页引用、能回答细节问题（"英语四六级加几分"）的知识库。

> 文中的人名、机构名与文件名均为化名/示例；截图使用仓库自带的虚构语料（`tools/eval/fixtures/points-fixture.pptx`），不包含真实数据。

| 聊天：流式回答 + 逐页引用 | 证据抽屉：点引用定位到页 |
|---|---|
| ![聊天](docs/images/chat-answer.png) | ![证据](docs/images/chat-evidence.png) |

![界面演示：回答 → 证据 → 文件 → 资源](docs/images/demo.gif)

---

## 这个仓库交付了什么

不是"把开源项目跑起来"：仓库累计 **46 个提交、343 个源文件改动**（不含构建产物与 lock），围绕一条完整的文档问答链路做了四块工作：

- **数据入口**：修复默认配置下检索被静默跳过、扫描件正文未入库、`.docx` 索引失败三类缺陷；新增按页决策的 OCR 抽取器。
- **检索与评测**：自建只跑检索层、零 token 成本的评测，用同一套题驱动切块、重排、拒答闸门和向量模型选型。
- **全栈重构**：把单页应用替换为 React 18 + FastAPI `/api/v1`（39 个接口、SSE 流式、HttpOnly Cookie、管理员 RBAC），并保留 `/legacy` 回滚路径。
- **工程化**：399 个 Python 用例 + 43 个前端单测进 CI、一键启动、`doctor` 自检、查询 trace 与 token 记账。

逐条证据、定位过程和实测数字见 [MODIFICATIONS.md](MODIFICATIONS.md)。

---

## 亮点速览

| 做了什么 | 可验证的证据 |
|---|---|
| 修复**检索静默失效**：默认配置下召回恒为空，模型绕过文档凭记忆作答 | 同一条默认路径：修复前召回 0 条 → 修复后正确命中并带引用（[§2.5](MODIFICATIONS.md#25-验证证据)） |
| 新增**扫描件 OCR 检索链路**：文字层只有标题时按页 OCR 后再入库 | 同一份 PDF 正文从 **209 字符 → 2322 字符**，问题「英语四六级加几分」得到「四级 +4 分 / 六级 +6 分」并引用 `[第 2 页]`（[§2.7](MODIFICATIONS.md#27-同类缺陷二扫描版-pdf-的正文根本没进索引)） |
| 上游**无 i18n 机制**下做中文界面：译文不落源码 | **336** 条词条、**296** 处标签本地化，剩余 18 条为刻意保留的品牌/标识符（[§3](MODIFICATIONS.md#三界面汉化引入翻译库译文不入代码)） |
| **全栈重构**：Gradio 单页 → React 18 + FastAPI `/api/v1` | **39** 个接口、SSE 流式、HttpOnly Cookie、管理员 RBAC；**57** 个 API 测试 + **43** 个前端单测；首屏 JS **272.11 kB** gzip；`KH_WEB_UI=0` 可回滚（[§5.25](MODIFICATIONS.md#525-第二代前端react-spa--fastapi2026-10-18) / [§5.29](MODIFICATIONS.md#529-m4-起步模型供应商与-mcp-的增删改2026-10-19)） |
| 建立**检索评测**（只跑检索层，零 token 成本） | 私有 27 题 + 12 无答案：Hit@1 **59.3% → 88.9%**（单文件）、MRR 0.702 → **0.933**；公开 9 题可复现 Hit@1 **87.5%** / MRR **0.900**（[评测](#检索评测)） |
| 让评测**在干净环境可复现** | 仓库自带 5 页示例语料 + 9 题配套题集 + 结果文件；配套单测保证"题目引用的页/事实"真的在那份语料里（`tools/tests/test_fixture_eval.py`） |
| 向量模型**用评测选型**，而不是凭感觉 | 4 个候选模型横向对比，Hit@1 从 **36.7% → 60.0%**（30 题版本实测） |
| 向量化可切换：**通义 API（默认）** 或 **本地 ONNX**（离线兜底） | 通义与本地 mpnet 指标相当（Hit@1 均 60.0%，30 题版本），前者省掉 1 GB 本地模型 |
| **成本与延迟可量化**：默认关闭"每个召回块调一次 LLM 打分" | 1 次调用 / **3291 token**（关）vs 11 次 / **9043 token**（开）；检索 P50 约 **1.6 s**（[§5.10](MODIFICATIONS.md#510-成本与延迟每题的-token-与-p50p95)） |

自动化测试 **399 个 Python 用例 + 43 个前端单测**全绿，全部离线运行（不联网、不调用模型）；CI 每次 push 都会跑一遍。

---

## 架构

```
浏览器
├─ /            React 18 + TypeScript + Vite（web/dist 已提交，运行时不需要 Node）
├─ /api/v1/*    FastAPI：JSON + SSE（ktem/api → ktem/services，39 个接口）
└─ /legacy/     经典 Gradio（迁移期回滚；KH_WEB_UI=0 时回到根路径）

                         │ 会话 / 检索范围 / 证据
┌────────────────────────▼──────────────────────────────┐
│ ktem 应用层：会话管理、检索、引用、设置、资源、用户    │
└────────┬───────────────────────────────────┬──────────┘
         │ 索引                               │ 检索
┌────────▼───────────────────┐      ┌────────▼──────────────┐
│ 文件抽取                    │      │ 混合检索                │
│  · PDF：OCRPDFReader       │      │  · 向量库（通义/本地）   │
│    ├ 文字层足够 → 直接用    │      │  · LanceDB 文档库        │
│    └ 扫描页 → 本地 OCR     │      │  · top_k / 重排 / 拒答   │
└────────┬───────────────────┘      └────────┬──────────────┘
         │ 向量化                              │
┌────────▼───────────────────────────────────▼──────────────┐
│ 向量化：通义 text-embedding-v3（默认，API）                  │
│        或本地 FastEmbed（离线兜底）      对话：DeepSeek（API） │
└────────────────────────────────────────────────────────────┘

界面文案：libs/ktem/ktem/assets/i18n/zh.json（Gradio）+ web/src/lib/i18n.ts（React）
```

路由只做鉴权、参数校验与序列化，业务在 `ktem/services/*`（不 import gradio，因此能脱离 UI 单测）；`app.py` 负责装配 `/`、`/api/v1` 与 `/legacy`。会话使用 HMAC 签名的 HttpOnly Cookie，管理员接口统一 `admin_required`，供应商列表不返回 `spec`（API key 只在管理员单条详情里）。

---

## 三个值得讲的问题

### 1. 检索静默失效：功能"配了"，但没生效

默认配置下提问，界面一切正常、模型也能给出像模像样的答案，**但引用栏是 `No evidence found.`** —— 检索被整段跳过，模型在用训练记忆作答。

根因是两处叠加的状态缺陷：检索范围单选框的默认值不在可选项集合内（UI 呈"未选中"），以及全库检索分支依赖一个只在用户手动点击后才会刷新的陈旧 `gr.State`。两者都让 `doc_ids` 变空，而 `pipelines.py` 里 `if not doc_ids: return []` 直接短路。

修复：默认值改为合法值、把会话中的权威 `user_id` 透传给选择器，覆盖 File 索引与 3 个 GraphRAG 分支，并把选择器逻辑抽成纯函数以便单测。

### 2. 扫描件：正文根本没进索引

用户上传的制度文件是**扫描件**：4 页只抽出 209 个字符，而且抽出来的是各级标题（`⼀`/`⼆` 还被抽成「康熙部首」码位，U+2F00）。正文是图片，而 DeepSeek 是纯文本模型。

导出索引块后一目了然：4 个 37–59 字符的标题块 + 4 个 `Page thumbnail` 图片块，**正文 0 字符**。

修复：新增 `OCRPDFReader`，**按页决策**——文字层 ≥ 200 字符直接用（数字版 PDF 零开销）；不足则渲染 200 DPI 交给本地 OCR（PP-OCR，跑在已装的 onnxruntime 上，无 PyTorch，模型随 wheel 自带，全程离线）；OCR 失败则保留原文字层，绝不把页面变空。

### 3. 上游没有 i18n，译文又不能写进源码

Gradio 4.39 没有 `gr.I18n`，界面文案散落在 20 多个文件里。做法是一条「采集 → 外部翻译 → 词表缓存 → 回写」的流水线，但难点在于**有三类串绕开了组件树**：

| 通道 | 例子 | 处理 |
|---|---|---|
| Python 运行时拼装 | `[Page {}]`、`相关性分数` | `tr()` 包裹 |
| 事件回调里的字面量 | `Indexing completed.` | `tr()` 包裹 |
| 浏览器端拼装 | `version:`、`Browse conversation` | 注入 `window.__KTEM_t` |
| 事件弹窗 | 约 50 条 `gr.Info/Warning/Error` | 只改 3 个入口的钩子 |

其中踩过一个把整个前端搞挂的坑：把词表**拼在 `gr.Blocks(js=...)` 前面**会导致 Gradio 的函数表达式包装语法错误，整段脚本一行不执行 → 登录框永不出现。最终改为注入 `<head>`，并补了回归测试（[§3.5](MODIFICATIONS.md#35-运行时字符串三条绕开组件树的通道)）。

---

## 检索评测

评测只跑**检索层**：不调用任何模型，因此零 token 成本，换模型/换切块/换重排都能直接量化对比。

**新 clone 先用自带示例语料复现一次**（不依赖任何私有文件）：

```powershell
# 语料是 5 页 PPTX（虚构内容），已随仓库提交；也可以用 tools/eval/make_fixture.py 重新生成
# 1) 把它上传进「文件集合」并等索引完成（需要向量化：通义 text-embedding-v3 或本地 FastEmbed）
# 2) 跑配套的 9 题（含 1 道无答案题）
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\fixture-points.json
```

评测集与语料的一致性有单测兜底（`tools/tests/test_fixture_eval.py`：题目引用的页码必须存在、
每个关键事实必须真的出现在那份语料里），所以「题目跑出来的数字」不会因为语料被改而悄悄漂移。

公开示例语料的实测（8 道可答题 + 1 道无答案，5 个块；本机通义 `text-embedding-v3`）：

| Hit@1 | Hit@3 | Hit@5 | MRR | 关键事实覆盖 | 无答案拒答 | 可答题误拒 | P50 |
|---|---|---|---|---|---|---|---|
| **87.5%** | 87.5% | **100%** | **0.900** | **100%** | **100%** | 12.5% | 493 ms |

结果文件：[`tools/eval/results-public.md`](tools/eval/results-public.md)、
[`results-public.json`](tools/eval/results-public.json)。数字会随向量模型变化，所以它证明的是
**链路与题集可复现**；效果数字以私有 27 题为准，两者口径不要相加或混用。

在**自己的语料**上评测（27 条问题；切块 512/64，默认重排）：

```powershell
# 先把语料上传进「文件集合」，然后（应用需停止，二者共用 sqlite / LanceDB）
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json `
    --corpus "你的语料.pdf" --out tools\eval\results.md --json tools\eval\results.json
```

当前基线（27 条问题；切块 **512/64**，默认重排）：

| 检索范围 | 块数 | Hit@1 | Hit@3 | Hit@5 | MRR | 关键事实覆盖 |
|---|---|---|---|---|---|---|
| 只检索该 PDF（`--scope`） | 11 | **88.9%** | 96.3% | **100%** | **0.933** | **100%** |
| 全库（含 1 万块表格） | — | **77.8%** | 88.9% | 88.9% | 0.847 | 81.5% |

> 历史口径对照：**按页成块 + 不重排**（`chunk_size=0`、`--rerank off`）时同一套题是
> Hit@1 55.6% / MRR 0.707（单文件）、59.3% / 0.702（两文件 8 块）。也就是说"只改切块"把
> Hit@1 提了 **33.3 个百分点**。

> 评测集里的语料文件名与机构信息已做脱敏处理；在你自己的语料上运行，用
> `--corpus "你的文件名"` 覆盖评测集里的 `corpus` 字段即可。

#### 切块粒度（实测 A/B）

`chunk_size=0` 时按"页"成块，一页约 500–650 字。改成 **512/64**（token）后同一份材料从 4 块变 11 块：

| 切块 | 块数 | Hit@1 | MRR | facts |
|---|---|---|---|---|
| 按页（0） | 4 | 55.6% | 0.707 | 100% |
| **512/64（现默认）** | 11 | **88.9%** | **0.933** | 100% |

配置项：`FILE_INDEX_PIPELINE_SPLITTER_CHUNK_SIZE` / `..._CHUNK_OVERLAP`，设 0 恢复按页成块；
**改完必须重建索引**（`tools/reindex_corpus.py`）才对已有文件生效。

#### 语料规模的影响（实测）

把一个 **10237 块**的表格（10 MB 招考简章）放进同一个索引，同一套 27 题：

| 切块 | 只检索该 PDF | 全库检索 | 差距 |
|---|---|---|---|
| 按页（0） | Hit@1 55.6% / facts 100% | Hit@1 33.3% / facts 48.1% | **−22.3 / −51.9 个百分点** |
| 512/64 | Hit@1 88.9% / facts 100% | Hit@1 77.8% / facts 81.5% | −11.1 / −18.5 个百分点 |

两个结论：① 粗切块会**放大**"大文件摊薄小文件"；② 细切块后差距缩小一半，但没消失——
按文件配额 / 多样化重排仍是待办（[ROADMAP.md](ROADMAP.md) B 组）。

复现：

```powershell
# 全库
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json `
    --corpus "你的语料.pdf"
# 限定范围（等价于界面上的「在文件中搜索」）
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json `
    --scope "你的语料" --corpus "你的语料.pdf"
```

#### 成本、延迟与查询 trace

每题的成本是可测的，不是估的：打开 trace，问几题，再聚合（ROADMAP C3/C4）：

```powershell
$env:KH_QUERY_TRACE="1"     # 写到 ktem_app_data/query_trace.jsonl（也可以在 .env 里设）
# …在界面里问几题…
.\.venv\Scripts\python.exe tools\trace_report.py                  # 请求数/拒答率/P50/P95/token
.\.venv\Scripts\python.exe tools\trace_report.py --last 20 --json out.json
```

实测（6 题、真实 DeepSeek 调用）：

| `use_llm_reranking` | 每题 LLM 调用 | 每题 token | P50 | P95 |
|---|---|---|---|---|
| **关（现默认）** | **1.0** | **3291** | 2564 ms | 3530 ms |
| 开 | 11.0 | 9043 | 2955 ms | 4027 ms |

`use_llm_reranking` 是"每个召回块各调一次 LLM 打相关性分"，只影响证据面板排序与低相关提示，
却让每题多 **10 次调用 / +175% token**。所以默认关掉（`USE_LLM_RERANKING=true` 可开回）。
token 数来自 provider 返回的 usage（流式最后一帧也计），provider 不返回时记 0，不做估算。

#### 拒答闸门（无答案问题不再硬答）

检索最高分低于 `KH_ABSTAIN_SCORE_THRESHOLD`（默认 **0.45**）时，聊天页直接回答
"知识库没有依据 + 下一步建议"，**不调用模型**；被拦截的查询记进
`ktem_app_data/abstained_queries.jsonl`。阈值不是拍脑袋：用 12 道"语料里没有答案"的题校准：

| 阈值 | 无答案题正确拒答 | 可答题误拒 |
|---|---|---|
| 0.42 | 75.0% | 0% |
| **0.45（默认）** | **91.7%** | **0%** |
| 0.53 | 100% | 开始误伤（最低正分 0.473） |

```powershell
# 校准命令（T4 无答案集）
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-no-answer.json
# 可答题的误拒率
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json `
    --corpus "你的语料.pdf"
```

> 局限：闸门只看检索分数，不做语义判断——同义但低分的问法会被误拒，
> "看似相关、其实回答不了"的题仍可能通过。答案级校验在 C 组（未做）。
> 竖排表格（PDF 一格一行）与"关键词命中挤掉高分块"这两个漏洞已修，见下面的 §5.19。

**表格语料补充（2026-10-17）**：一行 `学号,姓名,学时` 与自然语言问题的向量距离天然偏远，
单一阈值会把"表里有这个人"的题也拒掉（实测 0.38 < 0.45）。所以闸门多一层判定：
如果问题里的**实体词**（3 字人名、学号等）逐字出现在某条召回的**表格式行**里，且该词只出现在少数块中，
那么分数低到 `KH_ABSTAIN_TERM_FLOOR`（默认 **0.33**）仍然作答；`0` 可关闭该放宽。
同一份 xlsx（界面「在文件中搜索」口径）实测：可答题误拒 **6/10 → 3/10**，
"陈志强"这类表里没有的名字仍被拒；无答案集回归仍 **91.7%**。
拒答文案已本地化（`zh` 下显示中文，不再是英文原文）。

**但"没匹配到正确的文档"还有另一半原因**：一次向量查询在全库排序，1 万块的表格会把
小表格挤出候选（实测：问"李同学"时上下文里根本没有那份 xlsx）。现在检索多一步
**按文件补齐**：被选中却"一个块都没进结果"的文件，单独为它查一次，并让每个文件最好的块
优先占位（`KH_RETRIEVAL_PER_FILE`，默认开）。实测同一问题：上下文从 1–2 个文件变成 **4 个**，
李同学那题从拒答变成作答；代价是检索 P50 **1076 → 1347 ms**（+25%，只在确有文件缺席时发生）。
详见 [§5.13](MODIFICATIONS.md)。

**文件档案 + 按文件路由（§5.14）**：每个文件索引完成时会留一条
「文件：<名字> 内容摘录：<首/中/尾摘录>」写进 `Source.note["summary"]`（不调模型、重建可复现，
老文件在第一次检索时自动补齐）。提问时先用问题向量和这些档案比余弦，只检索
**得分 ≥ 最高分 80%** 的文件（至少 2 个、最多 3 个；低于 0.30 不路由）。
实测 4 个文件：四个问题的首选文件**全部正确**，检索从 4 个文件收敛到 2–3 个，
延迟中位数 **1568 → 1279 ms（−18%）**，答案判定不变。开关 `KH_FILE_ROUTING`（默认开）；
档案缺失或分数不达标时自动退回全量检索，不会让问题变得答不出来。

**档案的盲区：它知道"这文件讲什么"，不知道"里面有没有这个人"（§5.20）**：成绩表在向量空间里
就是一堵数字，档案相似度只有 0.4365，而奖学金通知是 0.6267——0.80 的相对门槛把成绩表筛掉了，
于是问「李同学的综测可以评国家励志奖学金吗」时，检索范围里**根本没有那张表**（日志
`file routing: 6 -> 2 files`），模型只能说"材料里没有"。现在路由多一条：一次**全库全文查询**
找出"实体词落在表格行/单元格里"的文件（名字被切 3 字窗口，`李同` 命中 `李同学`），
补回路由范围。上限：最多补 2 个、且只补 ≤500 块的文件（1 万块的招考简章会把候选挤爆），
`KH_ROUTING_ENTITY_FILES=0` 可关。实测该题 6 → **4** 个文件、上下文里出现李同学的综测行；
27 题事实覆盖与误拒率保持 **96.3% / 3.7%**，P50 434 → **405 ms**（不调用嵌入）。

**"答案要跨几个文件"的最后一层：这个人那一行，以及面板上的 0.0（§5.21，2026-10-18）**：问
「某人能评上校级三等奖学金吗」时，上面那条补丁把名额花在了**已经在范围里**的通知上——问题里的
3 字窗口 `奖学金`/`三等奖` 也会落进通知的表格行，真正指向某一行的 `张同学` 反而没名额了；
就算表在范围里，进上下文的也是表里向量分最高的那几行，不是这个人那一行：**"这个人在哪一行"
不是相似度问题**（行 0.351，条件段落 0.488）。现在多加一步**实体行补齐**：在用户的完整选择上做一次
全文查询，只认"**行标识**落在**单元格**里"的词——`24405010135 张同学 75.45…` 算，
`一等奖学金:综测…` 这种散文不算，`三等奖` 这种在同一块里重复十次的列值也不算（4 字名只以
`欧阳明` 窗口出现时，短单元格里包含窗口同样算）；每个文件最多 1 块、默认最多 3 块，放到上下文最前
并**单独占名额**（`KH_ENTITY_ROWS` 默认 **3**，`0` 关闭；`KH_ENTITY_ROW_MAX_CHUNKS` 默认 **0** =
不限）。实测该题上下文 10 块/3 文件 → **13 块/5 文件**，同一提示词下回答从「无法确定，没有综测
数据」变成引用综测排名 6、学业排名 4、实践 32 学时并给出"具备申报资格"；跨文件 16 题事实覆盖
**13/16 → 16/16**（本机私有语料，题集不随仓库提交，口径见 §5.21），27 题指标与无答案拒答不变。
同一个改动修好了信息面板：它只读 LLM/Cohere 的分数键，而本地重排器写的是 `rerank_score`，
所以过去**每一块都是 `[得分: 0.0]`、`相关性分数: 0.0`**；现在按 LLM 分 > 重排分 > 向量相似度取值。

**问「代码里是什么算法」被拒（§5.22，2026-10-18）**：代码文件（`代码.txt`，`TxtReader`）入库正常、
块也在上下文里，但**代码与中文问题在向量空间里离得远**（最佳 0.35–0.39，散文类 0.5–0.7），
全局散文阈值把"问的就是这份文件"的问题也拒了——这是 §5.8「表格里的数字」的对偶。
现在闸门多一条**结构性证据**：问题里出现**所命中文件的名字**（去扩展名、去空白标点后原样出现，
如 `代码` 对应 `代码.txt`）时，门槛降到 `KH_ABSTAIN_TERM_FLOOR`（0.33）；长文件名不会被误命中，
`0.30` 这种更弱的不放行。实测三种问法从拒答变成作答
（同一提示词下答出"线性基函数模型 + 高斯(RBF)/Sigmoid/傅立叶基函数 + 正则化对比"）；
27 题与无答案拒答不变（口径见 §5.22）。

**"相关和不相关的得分差不多"（§5.23，2026-10-18）**：面板里 `代码.txt` 的块 0.35、不相关的
《积分细则》块 0.31，看着一样。原因是**两种分数混在一列**：本地重排器比中文字词，代码是英文
标识符，重排分全是 0，面板就回落到向量相似度——于是"重排器判 0 的块"显示 0.31，"重排器认的块"
显示 0.29。修法三条：重排时把**文件名**计入评分（问题点到文件名，这个文件的每块都沾光）；
面板**重排器跑过就用它的分（包括 0.0），没跑过才用向量分**；未引用的块**按这个分降序**排列
（原来按默认恒为 0 的 LLM 分排，等于按 `set` 顺序）。实测同一题：相关块 0.29/0.12，
不相关块 **0.00**；27 题 / 跨文件 16 题 / 无答案拒答均不变。

**中文全文索引（§5.15，重要修正）**：关键词通道原来用 `en_stem` 分词——中文整句是一个 token，
所以对任何中文问题都返回 0 条（日志里的 `Got 0 from docstore`），混合检索退化成"只有向量"，
**名字/学号这类精确匹配一直靠不住**。现在改用 n-gram（2–3 字）分词，老库第一次查询时自动重建
（10267 块约 3 秒）。实测：`doc_store.query("李同学")` 从 0 条变成 2 条；问「李同学的社会实践完成得怎么样」
从拒答变成**按行作答**（已修 32 / 待修 0，与表格一致），"表里没有的人"仍被拒答；无答案集回归仍 **91.7%**。
代价：关键词命中最多占一半上下文名额（否则闸门没有相似度可判），全文候选只取 20 条（检索 3.2 s → **1.6 s**）。

**竖排表格 + 小选集关键词（§5.19，2026-10-18）**：现场问「李同学进省赛了吗」被拒答（**0.412** < 0.45），
而正确答案就在检索第一名那块里。三个叠加的缺陷一起修了：
① 闸门的实体词放宽只认"横排表格行"，而 PDF 读取器是**一格一行**（`李同学` 单独占一行），
于是补了"整行恰好等于该实体词"的判定；
② `docstore.query` 的范围过滤写成 `prefilter=True`，Lance 原生 FTS 对小选集**直接返回 0 条**
（只限定 6 个块时 0 条，改成后置过滤后 1 条）——关键词通道"选集越小越哑"；
③ 关键词命中原来排在最前，②一修就把真正的高分块挤出上下文（27 题：事实覆盖 96.3% → **63.0%**，
误拒 3.7% → **59.3%**），现在改为**排在相似度命中之**后，只补剩下没被占满的名额。
实测：现场三题误拒 **66.7% → 0%**，无答案集 **91.7% → 91.7%**，27 题事实覆盖与误拒率回到基线。

**选择器空选择（§5.16）**：上传文件会刷新文件下拉框并清空它的值，于是「在文件中搜索」模式下后端收到
**空的文件列表** → 检索器直接返回 0 条 → 聊天回答「知识库中没有依据（**最佳匹配得分 0.00**）」，
而文件其实好端端地在库里。现在空选择**回退为全部文件**（日志里会打印一行说明），
只有 `disabled` 模式才真的不检索。审计日志 `abstained_queries.jsonl` 里的 `best_score: 0.0`
就是这类"压根没查"的信号。

**想看每个文件的档案？**（§5.17）两个入口：

1. **「文件集合」页表格新增 `profile` 列**（中文界面叫「文件档案」），一行摘录；
2. 命令行（只读 sqlite，不改数据）：

```powershell
.\.venv\Scripts\python.exe tools\file_profiles.py            # 全部文件
.\.venv\Scripts\python.exe tools\file_profiles.py --name 综测 # 按名字过滤
.\.venv\Scripts\python.exe tools\file_profiles.py --json out.json --full
```

输出形如：

```
■ 某班级学年综测汇总表.xlsx
  块数 8 / 向量 8 / loader PandasExcelReader / tokens 2340
  档案：学年：2025-2026学年 班级：某班级 … 学号 姓名 第一学期学业成绩测评 …
```

档案本身存在 `ktem_app_data/user_data/sql.db` 的 `index__<id>__source.note["summary"]` 里；
老文件没有档案时，第一次检索会自动补齐。

**表格列不再挤在一起（§5.18）**：两个原因——① Gradio 的 `column_widths` 把裸数字当**像素**
（`[0,50,8,...]` 实际是 `50px`，长文本必然被裁）；② `main.css` 里资源页 `max-width: max(70vw,1200px)`，
1535px 屏幕上两侧各空 230px。现在：列宽全部改百分比、`wrap=False`（一行一个文件，行高正常）、
文件表高度 420px，`文件档案` 列放 40 字摘录（**完整档案在选中文件后显示在下方详情区**），
并把资源页宽度放宽到 `max(92vw, 1400px)`（可用宽度 ~1074px → ~1412px）。
其它同类表格（索引、模型、向量模型、重排、MCP、论文推荐、用户列表）也一并换成百分比。


### 向量模型选型（评测驱动）

同一套评测、同一份语料，只改向量模型（下表为**当时的 30 题版本**，与上方 27 题基线不可直接相减）：

| 模型 | 维度 | 本地体积 | Hit@1 | Hit@3 | MRR |
|---|---|---|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2`（初版） | 384 | 0.22 GB | 36.7% | 73.3% | 0.589 |
| `paraphrase-multilingual-mpnet-base-v2`（本地，离线兜底） | 768 | 1.0 GB | 60.0% | 80.0% | 0.739 |
| **`text-embedding-v3`（通义 DashScope，现默认）** | 1024 | 0（API） | **60.0%** | 76.7% | 0.736 |
| `multilingual-e5-large`（带 E5 前缀） | 1024 | 2.24 GB | 53.3% | 73.3% | 0.683 |
| `multilingual-e5-large`（不带前缀） | 1024 | 2.24 GB | 46.7% | 70.0% | 0.642 |

结论：

1. 换掉 2020 年的 MiniLM 后 **Hit@1 提升 23.3 个百分点**（36.7% → 60.0%），只是换一个模型名；
2. **通义 v3 与本地 mpnet 基本持平**（Hit@1 都是 60.0%，MRR 0.736 vs 0.739），
   但通义不占本地磁盘、也不用下载模型 —— 所以默认走通义，本地模型作为离线兜底保留；
3. E5 系列**必须带 `query: ` / `passage: ` 前缀**：同一个模型，带前缀比不带高 6.6 个百分点。
   框架原本把查询和文档一起送进同一个接口、丢掉了这个区分，本仓库给 FastEmbed 封装补了
   `query_prefix` / `passage_prefix`。

> 切换方式：在 `.env` 里配 `DASHSCOPE_API_KEY` 即默认用通义（`text-embedding-v3`）；
> 不配则自动回落到本地 FastEmbed。**换向量模型必须重建索引**（维度不同），用
> `tools/reindex_corpus.py`。

**重排（已闭环，2026-10-17）**：默认 Cohere 缺 key 时不再空转——`is_available()` 检测到跑不了，
自动回退到**零依赖的本地词法重排**（中文字符 bigram 覆盖 + 拉丁词），并保留原检索相似度
（拒答阈值不失效）。同一套 27 题实测：

| 口径 | 重排 | Hit@1 | Hit@3 | MRR | P50 | P95 |
|---|---|---|---|---|---|---|
| 单文件（11 块） | off / on | 88.9% / 88.9% | 96.3% / 96.3% | 0.933 / 0.933 | 470 / 467 ms | 555 / 677 ms |
| 全库（含 1 万块表格） | off | 77.8% | 85.2% | 0.832 | 1053 ms | 1230 ms |
| 全库（含 1 万块表格） | **on** | 77.8% | **88.9%** | **0.847** | 1303 ms | 1615 ms |

结论：小语料无收益（如实记录），全库 **Hit@3 +3.7 个百分点、MRR +0.015**，代价 P50 +24%；
Hit@1 不变——词法重排能纠正第 2–3 名，纠正不了"第 1 名就错了"，那需要语义重排或检索配额。
详见 [MODIFICATIONS.md §5.9](MODIFICATIONS.md)。复现：`--rerank off` / `--rerank on`。

---

## 2 分钟演示

演示语料是仓库自带的 5 页虚构 PPTX（`tools/eval/fixtures/points-fixture.pptx`），不涉及任何真实文件：

1. 双击 `start.bat`，打开 `http://127.0.0.1:7860`，登录 `admin` / `admin`。
2. 「文件」→ 上传 `tools/eval/fixtures/points-fixture.pptx`，等索引完成。
3. 「对话」→ 问「英语四级和六级分别加几分？」→ 回答给出「四级 +4 分 / 六级 +6 分」，引用标记为上标 `1`。
4. 点引用标记 → 右侧证据抽屉定位到第 2 页（36% 相关性、片段原文）；再问「这份细则的满分是多少分？」验证跨页引用。
5. 「资源」看索引 / 模型 / 用户管理；「设置」看 schema 驱动表单；`/legacy/` 是随时可回滚的经典界面。

演示数据隔离：用 `KH_APP_DATA_DIR=<临时目录>` 启动，测试、截图与索引都不会写进真实的 `ktem_app_data/`。

---

## 快速开始

**双击 `start.bat`** 就能启动（Windows）。它会调用 PowerShell 脚本并绕过执行策略，
失败时窗口停住让你看到错误——`.ps1` 本身双击是**不会执行**的（Explorer 用记事本打开它，
或者在执行策略下被静默拦掉），这也是为什么需要这个 `.bat` 壳。

```powershell
# 等价命令（在项目根目录）
.\start.bat                     # 环境已存在就直接启动（不再每次跑 uv sync）
.\start.bat -ForceSync          # 强制重新同步依赖（首次部署 / 换了 lock 之后）
.\start.bat -SkipSync           # 明确跳过同步（同默认行为）
.\start.bat -NoStart            # 只准备环境，不启动

# 也可以直接调 PowerShell 脚本（可带 -NoStart / -SkipSync / -ForceSync）
.\scripts\bootstrap_windows.ps1
```

一键脚本做的事：检查 Python 3.10 → **仅当 `.venv` 不存在（或加了 `-ForceSync`）才 `uv sync`**
（跳过无 Windows 轮子的 llama-cpp-python）→ `.env` 不存在才从 `.env.example` 复制（**绝不覆盖**）→
把 `TMP`/`TEMP`/`THEFLOW_TEMP_PATH` 指到仓库内 → **等端口就绪后自动打开浏览器** → 启动。

浏览器是**端口返回 200 之后**才打开的（不是启动瞬间），所以不会出现"页面还没起来 → 连接被拒绝"的空标签页；
脚本会把结果写进 `ktem_app_data/logs/browser.log`（`opened …` / `timeout …`）。
不想要浏览器就用 `-NoBrowser`；端口被占用时改 `GRADIO_SERVER_PORT=7861` 再启动。

**启动失败先看日志**（窗口关掉也不怕）：

| 文件 | 内容 |
|---|---|
| `ktem_app_data/logs/bootstrap-<时间>.log` | 启动脚本全过程（含 uv 自己的报错行） |
| `ktem_app_data/logs/app.log` | 应用本身的输出/异常栈（追加写） |

手动等价步骤：

```powershell
# 1. 环境（必须 Python 3.10）
uv python install 3.10
uv sync --python 3.10 --no-install-package llama-cpp-python

# 2. 配置
Copy-Item .env.example .env
#   在 .env 里填 DEEPSEEK_API_KEY

# 3. 启动
.\.venv\Scripts\python.exe -X utf8 app.py
```

打开 <http://127.0.0.1:7860>，默认账号 `admin` / `admin`。

> **新 Web 界面在 `/`，经典 Gradio 界面保留在 `/legacy/`。**
> 迁移期两套并存：回滚只需在 `.env` 里设 `KH_WEB_UI=0` 并重启，根路径就回到经典界面。
>
> 已迁移：`/login` `/chat` `/files` `/settings`（含账户改密）`/resources`（索引只读 / 模型资源
> **可增删改** / 用户管理）`/help`（关于 + 使用指南）。

### 前端开发（可选，运行应用不需要）

前端源码在 `web/`，构建产物提交在 `web/dist/`（打包发布时由
`scripts/build_web.ps1 -CopyToPackage` 复制进 `libs/ktem/ktem/web/dist/`），**运行时不需要 Node**。
只有改前端时才需要：

```powershell
cd web
# 受限/沙箱环境里 npm 默认缓存不可写，先指到仓库内
$env:npm_config_cache = "D:\Code\VibeCoding\kotaemon\ktem_app_data\tmp\npm-cache"
npm ci
npm run dev      # Vite dev server，代理 /api、/legacy、/file= 到 127.0.0.1:7860
npm run build    # 产出到 web/dist（提交这份产物）
```

- 改完前端必须 `npm run build`，Python 服务读的是 `dist`，不是 `src`。
- API 前缀 `/api/v1`，会话 Cookie `ktem_session`（HttpOnly）；接口清单与设计说明见
  [MODIFICATIONS.md §5.25](MODIFICATIONS.md#525-第二代前端react-spa--fastapi2026-10-18)
  与 [§5.29](MODIFICATIONS.md#529-m4-起步模型供应商与-mcp-的增删改2026-10-19)。
- 深色模式、会话、证据抽屉等前端状态说明见 `web/README.md`。

主要配置项（详见 [MODIFICATIONS.md §3.7](MODIFICATIONS.md#37-配置与使用)）：

| 配置项 | 默认 | 作用 |
|---|---|---|
| `KH_APP_DATA_DIR` | `./ktem_app_data` | 文档、SQLite、LanceDB、模型缓存与会话密钥的根目录；演示/测试时指向独立目录 |
| `KH_WEB_UI` | `1` | 根路径用 React SPA；设 `0` 回滚到经典 Gradio |
| `KH_UI_LANGUAGE` | `zh` | 界面语言；设 `en` 还原上游英文界面 |
| `KH_ANSWER_LANGUAGE` | 跟随界面语言 | 模型**回答**语言 |
| `PDF_OCR_ENABLED` | `true` | 扫描页走本地 OCR；`false` 回退到原抽取器 |
| `PDF_OCR_MIN_CHARS` / `PDF_OCR_DPI` | `200` / `200` | OCR 触发阈值与渲染精度 |
| `DASHSCOPE_API_KEY` | 空 | 配了就用通义 `text-embedding-v3` 做向量（默认）；不配则回落到本地 FastEmbed |
| `LOCAL_EMBEDDING_MODEL` | mpnet-base-v2 | 本地兜底向量模型（仅在没配通义 key 时使用） |

中文界面词表已随仓库提供（`libs/ktem/ktem/assets/i18n/zh.json`），**clone 下来就是中文**；
需要重新生成/更新时：

```powershell
.\.venv\Scripts\python.exe -m ktem.utils.i18n build --language zh --backend llm
.\.venv\Scripts\python.exe -m ktem.utils.i18n bundle --language zh   # 同步进仓库
```

---

## 测试

```powershell
# 先停掉应用（共用 sqlite / LanceDB）
.\.venv\Scripts\python.exe -m pytest libs\kotaemon\tests\test_ocr_pdf_reader.py `
    libs\ktem\ktem_tests tools\tests -q --ignore=libs\ktem\ktem_tests\test_qa.py
```

覆盖：检索范围选择器的纯函数不变式、PDF OCR 抽取器的按页决策、本地化层
（只改显示属性、选项值不丢、占位符不丢、`<script>` 不提前闭合、运行时模板回填、通知钩子）、
索引失败回滚与启动自愈（`ktem_tests/test_orphan_repair.py`）、向量批大小自适应
（`kotaemon/tests/test_embedding_batching.py`）、拒答闸门（`ktem_tests/test_abstain_gate.py`：
关键词哨兵不误拒、阈值边界、审计日志写失败不影响作答）、本地重排与回退
（`ktem_tests/test_local_reranker.py`）、`.pptx` 本地读取器（`kotaemon/tests/test_pptx_reader.py`）、
查询 trace 与用量计数（`tools/tests/test_trace.py`）、评测打分与自检判定（`tools/tests/`）、
按文件路由与实体证据（`ktem_tests/test_file_routing.py`）、实体行补齐与面板相关性分数
（`ktem_tests/test_entity_rows.py`、`ktem_tests/test_render_score.py`）、示例语料与题集的一致性
（`tools/tests/test_fixture_eval.py`）。

新增的 Web API / 前端托管契约（57 例，`MODIFICATIONS.md` §5.25–§5.29）：

```powershell
# 本机访问不到 huggingface.co 时先打开离线开关：否则 App() 会为重试
# Mixtral tokenizer 的 HEAD 请求多等约 90 秒（与功能无关，纯启动耗时）
$env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"

.\.venv\Scripts\python.exe -X utf8 -m pytest `
    libs\ktem\ktem_tests\test_api_auth_meta.py `
    libs\ktem\ktem_tests\test_api_conversations.py `
    libs\ktem\ktem_tests\test_api_chat.py `
    libs\ktem\ktem_tests\test_api_files.py `
    libs\ktem\ktem_tests\test_api_users.py `
    libs\ktem\ktem_tests\test_api_help_resources.py `
    libs\ktem\ktem_tests\test_api_vendors.py `
    libs\ktem\ktem_tests\test_evidence_channel.py `
    libs\ktem\ktem_tests\test_web_host.py -q -p no:cacheprovider

# `-p no:cacheprovider`：pytest 收尾写 .pytest_cache 要 mkdtemp，受限沙箱里会卡住；
# 普通机器可以省略。前端（需要 Node 18+；沙箱里先设 npm_config_cache）
cd web; npm test; npm run typecheck; npm run lint
```

实测：Python **399 passed**（其中 Web API 契约 57 例），前端 `npm test` **43 passed**；
typecheck / lint 均无告警。

新增模块的本地覆盖率（`coverage run -m pytest … && coverage report`，实测 321 个用例）：
`abstain.py` 100% · `selector.py` 100% · `routing.py` 100% · `file_profile.py` 100% ·
`llms/usage.py` 100% · `utils/trace.py` 98% · `rerankings/local_lexical.py` 98% ·
`loaders/pptx_loader.py` 82% · `index/file/repair.py` 80%；`i18n.py` 与 `ocr_pdf_loader.py`
的用例依赖 pytest 临时目录，需在 CI（Linux）上统计。

---

## 数字自证

README 里出现的每个数字都能用一条命令复现；"未测"就是未测，不写估计值。

| 数字 | 命令 | 证据 |
|---|---|---|
| 全库 Hit@1 77.8% / Hit@3 88.9% / MRR 0.847 / facts 81.5%（27 题，512/64 切块，默认重排） | **私有语料（含个人信息，未随仓库发布）**：`python tools/eval_retrieval.py --eval tools/eval/zh-points-rules.json --corpus "你的语料.pdf" --out tools/eval/results.md --json tools/eval/results.json` | [tools/eval/results.md](tools/eval/results.md)、[results.json](tools/eval/results.json) |
| 单文件（`--scope`）Hit@1 88.9% / MRR 0.933 | 上一条加 `--scope "你的语料"` | 终端输出；口径见本文件「切块粒度」 |
| 公开示例语料 9 题（8 可答 + 1 无答案）：Hit@1 **87.5%** / MRR **0.900** / 事实 **100%** | 上传 `tools/eval/fixtures/points-fixture.pptx` → `python -X utf8 tools/eval_retrieval.py --eval tools/eval/fixture-points.json` | [results-public.md](tools/eval/results-public.md)、[results-public.json](tools/eval/results-public.json)；一致性由 `tools/tests/test_fixture_eval.py` 守住 |
| 切块 A/B：55.6% → 88.9% | 同一套题，分别用 `chunk_size=0` 与 512/64 重建那份语料 | 本文件「切块粒度」、`MODIFICATIONS.md` §5.7 |
| 重排 A/B：Hit@3 85.2% → 88.9%，P50 1053 → 1303 ms | 同一套题，加 `--rerank off` / `--rerank on` | 本文件「重排」、`MODIFICATIONS.md` §5.9 |
| 拒答：无答案题 91.7% / 可答题误拒 0% | `python tools/eval_retrieval.py --eval tools/eval/zh-no-answer.json`（阈值见 `KH_ABSTAIN_SCORE_THRESHOLD`） | `tools/eval/zh-no-answer.json`、`MODIFICATIONS.md` §5.8 |
| 每题成本：1 次调用 / 3291 token（关 `use_llm_reranking`）vs 11 次 / 9043 token（开） | `python tools/trace_report.py --trace <trace.jsonl>`（先设 `KH_QUERY_TRACE=1` 问几题） | 终端表格、`MODIFICATIONS.md` §5.10 |
| 索引健康（文件数、块数、向量数、空块比例、配置是否真生效） | `python tools/doctor.py --json <临时路径>` | 终端表格；`--strict` 让 WARN 也返回非零 |
| 词表 336 条 | `python -m ktem.utils.i18n stats --language zh` | 终端输出 |
| 正文 209 → 2322 字符（扫描件 OCR） | `python tools/reindex_corpus.py --match "积分细则"` 后查 `Source.note` | `ktem_app_data/user_data/sql.db` |
| 测试通过数：Python **399** / 前端 **43** | 上面「测试」一节的 pytest 命令；`cd web; npm test` | 终端 / `.github/workflows/tests.yaml`（CI） |
| Web API 契约 **57** 例 / **39** 个接口 | `pytest libs\ktem\ktem_tests\test_api_*.py ...`；接口数：`grep -c '^@router\.' libs/ktem/ktem/api/*.py` | CI `tests` job；`libs/ktem/ktem/api/` |
| 首屏 JS **272.11 kB** gzip | `cd web; npm run build` | 构建输出 `dist/assets/index-*.js` |

> `tools/doctor.py` 的输出包含本机语料文件名，**不要把它提交进仓库**；
> 需要留档时写到仓库外，或先脱敏。

---

## 目录结构

```
├─ app.py                      FastAPI 宿主：装配 /（React SPA）、/api/v1、/legacy
├─ flowsettings.py             模型池、检索/语言/数据目录（KH_APP_DATA_DIR）默认值
├─ libs/kotaemon/kotaemon/
│  ├─ loaders/ocr_pdf_loader.py      OCR 感知的 PDF 抽取器
│  └─ loaders/                      各类文件抽取器（docx/pptx/xls/PDF）
├─ libs/ktem/ktem/
│  ├─ api/                     FastAPI 路由：auth/meta/chat/conversations/files/
│  │                           settings/users/resources/help/vendors（39 个接口）
│  ├─ services/                业务层（不依赖 gradio，可脱离 UI 单测）
│  ├─ utils/i18n.py            本地化流水线（采集 / 翻译 / 运行时 / JS 注入）
│  ├─ utils/selector.py        检索范围选择的纯逻辑（可单测）
│  ├─ assets/i18n/zh.json      中文词表（生成后入库）
│  ├─ index/file/              文件索引、抽取与检索管线
│  └─ pages/                   经典 Gradio 页面（保留在 /legacy）
├─ web/                        React 18 + TypeScript + Vite（src + 已提交的 dist）
├─ tools/
│  ├─ eval_retrieval.py        检索评测（分类指标 / 范围 / 重排 A/B / 退出码）
│  ├─ doctor.py                自检：文件是否真进了索引、配置是否真生效、检索 smoke
│  ├─ reindex_corpus.py        换模型或改切块后的索引重建
│  ├─ eval/                    评测集、基线结果与评测说明
│  └─ tests/                   工具链离线单测（CI 会跑）
├─ docs/images/                演示截图与 GIF
├─ start.bat                   双击启动（Windows；调用 scripts\bootstrap_windows.ps1）
├─ scripts/
│  ├─ bootstrap_windows.ps1    一键启动（Windows，纯 ASCII）
│  └─ download_pdfjs.sh        内置 PDF 阅读器脚本
└─ MODIFICATIONS.md            改造全过程记录（定位过程、实测数据、踩坑）
```

---

## 已知限制

- **`.xls` / `.pptx` 已修**：分别改走 pandas + `xlrd`（[§2.9](MODIFICATIONS.md#29-同类缺陷四xls老版-excel上传直接失败索引-0-块)）
  与 python-pptx（[§5.11](MODIFICATIONS.md)），不再依赖 `unstructured`。
  **`.doc`（老二进制 Word）仍走 `unstructured`**：python-docx 不支持它，本机也没有 LibreOffice。
- **大文件仍会摊薄小文件**：细切块（512/64）已把差距从 22.3 个百分点缩到 11.1，但没消失；
  按文件配额/多样化重排已经做了（§5.13/§5.20），代价是**大表里的某一行仍然搜不到**——
  实体补充只回补 ≤500 块的文件，1 万块的招考简章这类不进范围。
- **拒答闸门是分数闸门**：只看检索最高分（0.45），不做语义判断；有一个"实体词 + 表格式行/独占
  一行的单元格"的二级放宽（[§5.19](MODIFICATIONS.md)），但"实体在、属性不在"的问法仍会被放行
  （问体重、问不存在的名次）。答案级校验（C1）未做。
- **关键词通道只在名额有余时才生效**：中文全文索引现在对小选集也能命中（[§5.19](MODIFICATIONS.md)），
  但关键词命中没有相似度，为避免挤掉真正的高分块，它们只排在相似度命中之**后**补位；
  "按名字精确找行"靠的是这条通道，而"这句话能不能答"仍由向量分与闸门决定。
- **重排是本地词法重排，不是语义重排**：Cohere 无 key 时自动回退到零依赖的本地词法重排（§5.9），
  它能纠正第 2–3 名的顺序（全库 Hit@3 +3.7 个百分点），但对"第 1 名就错了"无能为力；
  真语义重排需要 cross-encoder（本机 fastembed 0.4.2 无该 API、HF 模型下载不通）。
- **索引失败现在不会静默**：失败会回滚、在文件列表显示原因，并在下次启动时自动重解析
  （见 [§2.10](MODIFICATIONS.md#210-根治解析索引失败不再变成幽灵文件并在启动时自动修好历史遗留)）；
  `tools/doctor.py` 可以随时核对"文件在列表里但检索不到"这类状态。
- **OCR 成本**：约 8 秒/页（200 DPI），仅扫描页触发。
- **向量化默认走通义 API**：需要网络与额度；离线场景可用本地 FastEmbed 兜底，
  但首次需下载约 1 GB 模型（`fastembed_cache` 已从仓库清理，可按需重新拉取）。
  通义单次最多 10 条文本，客户端会在服务端报错时自动采用这个上限。
- **重建过的旧文件，引用预览路径要重建一次才更新**：新上传/重建的文件，块元数据指向稳定的存储副本
  （`user_data/files/<hash>.<ext>`），预览可用（[§5.12](MODIFICATIONS.md)）；老索引里的指向是旧的临时路径，
  对非 PDF 已不再告警，PDF 需要 `tools/reindex_corpus.py` 重建一次。
- **评测数字的语料边界**：88.9% / 0.933 来自私有真实语料（含个人信息，未随仓库发布）；仓库自带的
  5 页虚构语料 + 9 题只用来验证"入库 → 检索 → Hit@k"链路可复现，不足以单独支撑效果结论。
- **管理员的索引新增/删除仍留在 `/legacy`**：这类操作会写库、需要重启并依赖失败回滚，新界面提供
  只读索引视图与文件级管理；`KH_WEB_UI=0` 是整站回滚开关。
- **单机单用户定位**：没有多租户、限流、高并发与生产监控；`doctor`/trace 面向本机排障，不是线上观测平台。
- 词表是机器翻译产物，个别术语（如 `Citation style`）可能需要人工润色，
  改 `ktem_app_data/i18n/zh.json` 即可覆盖仓库默认值。

---

## 许可与上游

本项目以 **Apache-2.0** 许可发布，许可证全文见 [LICENSE.txt](LICENSE.txt)。
仓库包含 kotaemon 项目的代码（Apache-2.0），上游版权归其作者；归属说明见 [NOTICE](NOTICE)，
本仓库的修改清单见 [MODIFICATIONS.md](MODIFICATIONS.md)。

改动的定位过程、实测数据与验证清单见 [MODIFICATIONS.md](MODIFICATIONS.md)，
后续演进计划见 [ROADMAP.md](ROADMAP.md)。
