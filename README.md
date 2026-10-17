# 引问 · CiteAsk

[![tests](https://github.com/wangwuqiang2026/citeask/actions/workflows/tests.yaml/badge.svg)](https://github.com/wangwuqiang2026/citeask/actions/workflows/tests.yaml)

文档问答系统：**扫描件与长文档可直接入索引，答案逐页可溯源，检索效果用评测驱动迭代。**

> Document QA with OCR-aware ingestion, page-level citations, and an evaluated retrieval pipeline.

面向的场景很具体：把一份**扫描版 PDF**（学校/单位的积分办法）变成可以按页引用、能回答细节问题（"英语四六级加几分"）的知识库。

---

## 亮点速览

| 做了什么 | 可验证的证据 |
|---|---|
| 修复**检索静默失效**：默认配置下召回恒为空，模型绕过文档凭记忆作答 | 同一条默认路径：修复前召回 0 条 → 修复后正确命中并带引用（[§2.5](MODIFICATIONS.md#25-验证证据)） |
| 新增**扫描件 OCR 检索链路**：文字层只有标题时按页 OCR 后再入库 | 同一份 PDF 正文从 **209 字符 → 2322 字符**，问题「英语四六级加几分」得到「四级 +4 分 / 六级 +6 分」并引用 `[第 2 页]`（[§2.7](MODIFICATIONS.md#27-同类缺陷二扫描版-pdf-的正文根本没进索引)） |
| 上游**无 i18n 机制**下做中文界面：译文不落源码 | **336** 条词条、**296** 处标签本地化，剩余 18 条为刻意保留的品牌/标识符（[§3](MODIFICATIONS.md#三界面汉化引入翻译库译文不入代码)） |
| 建立**检索评测**（只跑检索层，零 token 成本） | 27 条问题、Hit@1 **59.3%** / MRR **0.702**（[评测](#检索评测)） |
| 向量模型**用评测选型**，而不是凭感觉 | 4 个候选模型横向对比，Hit@1 从 **36.7% → 60.0%**（30 题版本实测） |
| 向量化可切换：**通义 API（默认）** 或 **本地 ONNX**（离线兜底） | 通义与本地 mpnet 指标相当（Hit@1 均 60.0%，30 题版本），前者省掉 1 GB 本地模型 |

自动化测试 **88 个用例**全绿，全部离线运行（不联网、不调用模型）。

---

## 架构

```
┌──────────────── Gradio 界面（中文，词表驱动）────────────────┐
│   聊天   │   文件集合   │   资源   │   设置   │   帮助       │
└─────────────────────────────┬──────────────────────────────┘
                              │ 事件 / 会话状态
┌─────────────────────────────▼──────────────────────────────┐
│ ktem 应用层：会话管理、检索范围选择、引用面板渲染           │
└────────┬────────────────────────────────────┬──────────────┘
         │ 索引                                │ 检索
┌────────▼───────────────────┐      ┌─────────▼──────────────┐
│ 文件抽取                    │      │ 混合检索                │
│  · PDF：OCRPDFReader       │      │  · Chroma 向量库         │
│    ├ 文字层足够 → 直接用    │      │  · LanceDB 文档库        │
│    └ 扫描页 → 本地 OCR     │      │  · top_k / MMR / 重排    │
└────────┬───────────────────┘      └─────────┬──────────────┘
         │ 向量化                             │
┌────────▼────────────────────────────────────▼──────────────┐
│ 向量化：通义 text-embedding-v3（默认，API）                  │
│        或本地 FastEmbed（离线兜底）     对话：DeepSeek（API） │
└────────────────────────────────────────────────────────────┘

词表：libs/ktem/ktem/assets/i18n/zh.json（生成后提交入库，clone 即中文）
```

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

```powershell
# 先把语料上传进「文件集合」，然后（应用需停止，二者共用 sqlite / LanceDB）
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json `
    --out tools\eval\results.md --json tools\eval\results.json
```

当前基线（27 条问题，语料 4 个页级块）：

| 指标 | 值 |
|---|---|
| 问题数 | 27 |
| 语料 | 2 个文件 / 8 个块（目标 4 块 + 干扰 4 块） |
| Hit@1 | **59.3%** |
| Hit@3 | **74.1%** |
| Hit@5 | **81.5%** |
| MRR | **0.702** |
| 关键事实覆盖率 | **81.5%** |

> 读法：`top_k=5` 时，库里**多出的无关文档会摊薄命中**——单个文件（4 块）时 Hit@5 是 100%，
> 加入第二个文件（共 8 块）后掉到 81.5%，Hit@1 基本不变、MRR 从 0.739 降到 0.702。
> 这正是「重排 / `top_k` 调参」要解决的问题，也是下一步的量化目标。

> 评测集里的语料文件名与机构信息已做脱敏处理；在你自己的语料上运行，用
> `--corpus "你的文件名"` 覆盖评测集里的 `corpus` 字段即可。

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

**下一步（仍是评测驱动）**：默认重排器是 Cohere —— 没有 API key，每次检索只打印
`Cohere API key not found. Skipping rerankings.` 然后原样返回。换成本地 ONNX cross-encoder 后，
用同一套评测对比 Hit@1 / MRR。

---

## 快速开始

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

主要配置项（详见 [MODIFICATIONS.md §3.7](MODIFICATIONS.md#37-配置与使用)）：

| 配置项 | 默认 | 作用 |
|---|---|---|
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
.\.venv\Scripts\python.exe -m pytest libs/kotaemon/tests/test_ocr_pdf_reader.py `
    libs/ktem/ktem_tests/ -q     # 先停掉应用
```

覆盖：检索范围选择器的纯函数不变式、PDF OCR 抽取器的按页决策、本地化层
（只改显示属性、选项值不丢、占位符不丢、`<script>` 不提前闭合、运行时模板回填、通知钩子）。

---

## 目录结构

```
├─ app.py                      启动入口：装配词表、构建 UI、注入 <head> 脚本
├─ flowsettings.py             模型池（DeepSeek / FastEmbed）与检索、语言的默认值
├─ libs/kotaemon/kotaemon/
│  ├─ loaders/ocr_pdf_loader.py      OCR 感知的 PDF 抽取器（本次新增）
│  └─ loaders/                      各类文件抽取器
├─ libs/ktem/ktem/
│  ├─ utils/i18n.py                  本地化流水线（采集 / 翻译 / 运行时 / JS 注入）
│  ├─ utils/selector.py              检索范围选择的纯逻辑（可单测）
│  ├─ assets/i18n/zh.json            中文词表（生成后入库）
│  ├─ index/file/                    文件索引、抽取与检索管线
│  └─ pages/                         各页面 UI
├─ tools/
│  ├─ eval_retrieval.py         检索评测脚本
│  └─ eval/                     评测集与基线结果
├─ docs/*.zh.md                 帮助页中文文档
└─ MODIFICATIONS.md             改造全过程记录（含定位过程、实测数据、踩坑）
```

---

## 已知限制

- **`.pptx` / `.xls` / `.doc` 仍走 `unstructured`**：它依赖系统 `libmagic`，在本机会 403。
  `.docx` 已改用本地 `DocxReader` 解决（见 [§2.8](MODIFICATIONS.md#28-同类缺陷三docx-上传成功但索引从未写入)）；
  其余格式需要时可按同样方式换成本地读取器。
- **切块粒度偏粗**：索引 `chunk_size=0`，扫描件按"页"成块（每页约 500–650 字），
  这是 Hit@1 偏低的主因之一。
- **重排未生效**：默认 Cohere 重排器缺 API key，检索后原样返回。
- **OCR 成本**：约 8 秒/页（200 DPI），仅扫描页触发。
- **向量化默认走通义 API**：需要网络与额度；离线场景可用本地 FastEmbed 兜底，
  但首次需下载约 1 GB 模型（`fastembed_cache` 已从仓库清理，可按需重新拉取）。
- 词表是机器翻译产物，个别术语（如 `Citation style`）可能需要人工润色，
  改 `ktem_app_data/i18n/zh.json` 即可覆盖仓库默认值。

---

## 许可

本项目以 **Apache-2.0** 许可发布，许可证全文见 [LICENSE.txt](LICENSE.txt)。

改动的定位过程、实测数据与验证清单见 [MODIFICATIONS.md](MODIFICATIONS.md)，
后续演进计划见 [ROADMAP.md](ROADMAP.md)。
