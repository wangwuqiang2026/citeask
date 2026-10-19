# 演进路线：从一个"能跑通"的改造，到一个"可被检验"的项目

> 文档状态：v1 · 基线为 `HEAD 9ad3e4e`（上游 #814）+ 工作区未提交改动（21 个已跟踪文件 `+412 −61`，12 个新增路径）· 2026-10-17

这份文档回答四个问题：**现在这个项目值多少分、还差什么、按什么顺序补、每一条怎么验收。**

它不描述"想法"，只描述可以验证的动作。每一节末尾都有验收标准，任何一条指标都必须能用一条命令复现。

---

## 1. 现在有什么

### 1.1 能力盘点

| 能力 | 具体做了什么 | 可验证证据 |
|---|---|---|
| 检索静默失效修复 | 默认配置下召回恒为空（选择器默认值不在可选集合 + 全库检索依赖陈旧 `gr.State`），模型绕过文档凭记忆作答 | 修复前后同一条路径可复现对比；`MODIFICATIONS.md` §2.1–§2.6 |
| 扫描件 OCR 入库 | 按页决策：文字层 ≥200 字符直接用，否则 200 DPI 渲染 + 本地 PP-OCR | 同一份 PDF 正文 **209 → 2322 字符**；`libs/kotaemon/kotaemon/loaders/ocr_pdf_loader.py`、`tests/test_ocr_pdf_reader.py`（7 例） |
| `.docx` 入库修复 | `unstructured` 依赖系统 `libmagic` 且会 403 → 换本地 `DocxReader` | 该文件 `note = {"tokens": 2429, "loader": "DocxReader"}`，4 个块（`MODIFICATIONS.md` §2.8） |
| 中文界面 | 上游 Gradio 4.39 无 i18n；自建「采集 → 翻译 → 缓存 → 回写」流水线，译文不落源码 | **336** 条词条、**296** 处标签；`libs/ktem/ktem/utils/i18n.py`、`assets/i18n/zh.json`、`ktem_tests/test_i18n.py`（44 例） |
| 模型接入 | DeepSeek 对话；向量默认通义 `text-embedding-v3`，本地 FastEmbed 兜底 | 5 组向量化方案横向对比（4 个模型，E5 带/不带前缀各一组，`MODIFICATIONS.md` §9.4） |
| 检索评测 | 只跑检索层、零 token 成本的 27 题评测 | Hit@1 **59.3%** / Hit@3 74.1% / Hit@5 81.5% / MRR **0.702** / 事实覆盖 81.5% |
| 工具链 | 换模型后的重建索引工具、评测脚本、启动入口 | `tools/reindex_corpus.py`、`tools/eval_retrieval.py`、`app.py` |
| 测试 | **88 passed**，全部离线（不联网、不调模型） | 对话 14 + 选择器 10 + i18n 44 + MCP 13 + OCR 7 |
| 体积治理 | 未用模型缓存 + 未使用 torch 清理 | 7.1 GB → **≈2.0 GB**（`MODIFICATIONS.md` §6.3） |

### 1.2 差距（本节是整份路线图的靶子）

下表每一条都经过检查确认，不是估计。

| # | 差距 | 为什么它重要 | 对应章节 |
|---|---|---|---|
| 1 | **工作不可见**：所有改动都在工作区，`HEAD` 仍是上游 commit；`origin` 指向上游，没有自有远程仓库 | 面试官 clone 下来只会看到"上游的一个 commit"，看不到你的工作 | A1 |
| 2 | **CI 覆盖不到核心改动**：`.github/workflows/unit-test.yaml` 末步是 `cd libs/kotaemon && pytest`，`libs/ktem/ktem_tests/` 从未被执行 | 88 个测试全靠本机自律，没有机器兜底 | A2 |
| 3 | **指标说服力不足**：语料 2 文件 / 8 块 / 27 题，单文件时 Hit@5 已经 100%（天花板效应） | 一个块的语料上加 1 个百分点毫无意义，无法支撑"重排/切块有效"的结论 | B1 |
| 4 | **重排是空配置**：默认 Cohere 但无 key，每次检索打印 `Cohere API key not found. Skipping rerankings.` 后原样返回 | 配置写着"开了"，实际没生效——和项目里已修的三处静默失效是同一类问题 | B2 |
| 5 | **切块粒度是"页"**：索引 `chunk_size=0`，扫描件每块约 500–650 字 | Hit@1 偏低的主因之一，且是典型的"可量化优化点" | B3 |
| 6 | **只有检索层评测**：没有答案级/引用级评测，没有 token 与延迟数据 | 讲不出"答得对不对、贵不贵、快不快" | C1 |
| 7 | **无演示素材、无一键启动**：没有截图/GIF/before-after；Docker CLI 有但 daemon 未启动，本机无法验证 build | 别人无法在 5 分钟内判断做得好不好 | A3 / A4 |
| 8 | **依赖引入不规范**：`rapidocr-onnxruntime` 无版本上界（仓库其它依赖都是区间）；`fastembed 0.4.2` 没有 cross-encoder，本地重排需要升级或自实现 | 供应链与可复现性问题，也是面试里"你怎么管依赖"的答案 | A1 / B2 |
| 9 | **两处"有代码但没接上"**：`use_llm_reranking` 默认开（每题额外对每个召回块调一次 LLM 打分）；`use_rewrite` 只绑定在 `regen` 状态上，多轮追问改写实际未生效 | 既是成本/延迟的可量化项，也是"读懂宿主框架"的证据 | C2 / C3 |
| 10 | **敏感信息**：`.env`、`ktem_app_data/` 从未进入任何 commit（`git log --all` 为空），但发布前仍需做一次确认性审计 | 一次泄露就毁掉整个项目 | A1 |

### 1.3 一句话自评

已经能讲三个有说服力的故事（静默失效定位、扫描件数据入口、无 i18n 框架下的本地化）；
缺的不是功能，而是**数字的可信度**（B 组）和**成果的可复现性**（A 组）。

### 1.4 进度总览（2026-10-17 收口）

| 计划项 | 状态 | 证据（命令 / 数字 / 文档） |
|---|---|---|
| A1 提交历史重构 + 自有远程 | ⬜ 未做 | 工作区仍有未提交改动与新增路径；未推送自有远程 |
| A2 CI 纳入 `ktem_tests` + 工具测试 + 覆盖率报告 | ✅ 完成（覆盖率门槛待 CI 验证） | `.github/workflows/tests.yaml`；本地实测新增模块覆盖率 78–100%（README「测试」） |
| A3 一键启动脚本 | ✅ 完成 | `start.bat`（双击入口，失败留窗 + 日志）+ `scripts/bootstrap_windows.ps1`（默认跳过 uv sync、`-ForceSync` 强制、端口就绪后自动开浏览器） |
| A4 演示素材 | ⬜ 未做 | 需要浏览器截图，仍缺 |
| A5 数字自证表 | ✅ 完成 | README「数字自证」一节 |
| B1 评测协议升级 | ◐ 工具与文档完成，语料/题量未扩 | `--category` / `--scope` / `--rerank` / `--fail-under-hit1` / `--abstain-term-floor`、退出码 0/1/2、`tools/eval/README.md`、`tools/tests/test_eval_retrieval.py` |
| B2 重排闭环 | ✅ 完成（本地词法重排，无模型） | 配置但不可用时自动回退；全库 Hit@3 85.2%→**88.9%**、MRR +0.015，P50 +24%（§5.9） |
| B3 切块 A/B | ✅ 完成 | 512/64 默认；**Hit@1 55.6% → 88.9%、MRR 0.707 → 0.933**（§5.7） |
| B4 拒答闸门 | ✅ 完成（表格语料已修） | 阈值 0.45 + 实体词/表格式行放宽（floor 0.33）：无答案题拒答 **91.7%**，表格可答题误拒 **6/10 → 3/10**，文案已中文化（§5.8） |
| B5 `doctor` 自检 | ✅ 完成 | `tools/doctor.py` 12 项检查 + `tools/tests/test_doctor.py`（17 例）；连它自己的过期告警也修了 |
| C3 成本与延迟 | ✅ 完成 | usage 记账 + `tools/trace_report.py`；实测 1 次/3291 token（关）vs 11 次/9043 token（开），默认关（§5.10） |
| C4 查询 trace | ✅ 完成 | `ktem/utils/trace.py`（`KH_QUERY_TRACE`）+ `tools/trace_report.py` + `tools/tests/test_trace.py`（12 例）（§5.10） |
| C5 更多本地读取器 | ◐ `.pptx` 完成；`.doc` 未做 | python-pptx 读取器 + `libs/kotaemon/tests/test_pptx_reader.py`（6 例）（§5.11）；`.doc` 仍需 LibreOffice |
| 引用预览失效（追加） | ✅ 完成 | 存储副本按 `<hash>.<ext>` 落盘 + `/file=` 白名单；实测返回 200 / application/pdf（§5.12） |
| 按文件补齐召回（追加） | ✅ 完成 | 小表格不再被大文件挤出：上下文覆盖 1–2 → **4** 个文件，李明辉那题从拒答变作答；P50 1076 → 1347 ms（§5.13） |
| 文件档案 + 路由（追加） | ✅ 完成 | 每文件存「文件：… 内容摘录：…」（老文件自动补）；按余弦只检索 2–3 个文件：首选文件 4/4 正确、延迟 1568 → 1279 ms（§5.14） |
| 中文全文索引（追加） | ✅ 完成 | `en_stem` 分词对中文恒返回 0 条 → 改 n-gram（老库自动重建）；姓名精确命中 0 → 2 条，按行作答，无答案集仍 91.7%（§5.15） |
| 选择器空选择（追加） | ✅ 完成 | 上传刷新会清空文件下拉框 → 检索器收到空列表、答「无依据 0.00」；空选择现回退为全部文件（§5.16） |
| 文件档案可视化（追加） | ✅ 完成 | 「文件集合」表格新增 `profile` 列 + `tools/file_profiles.py`（`--name/--json/--full`，只读）；11 例测试（§5.17） |
| 表格列宽修复（追加） | ✅ 完成 | `column_widths` 裸数字被 Gradio 当像素 → 全部改百分比、文件表 `wrap=True`、完整档案进详情区（§5.18） |

---

## 2. 定位：这个项目在简历里承担什么角色

### 2.1 它证明什么，不证明什么

**证明**：能读进一个陌生的大型开源框架、定位宿主框架自身的缺陷、在不改框架语义的前提下做产品化改造、并且用自建评测把效果量化下来。

**不证明**：模型训练/微调能力，从零设计 RAG 架构的能力，高并发线上运维能力。简历里不要往这些方向靠——经不起追问。

### 2.2 岗位映射

| 目标岗位 | 重点讲 | 可以弱化 |
|---|---|---|
| AI 应用 / RAG 工程师（首选） | 三处静默失效、评测驱动选型、重排/切块闭环、拒答闸门 | 部署细节 |
| 后端 / 平台 | 提交历史与 CI、doctor 自检、重建索引工具、成本与延迟 | i18n 实现细节 |
| 算法 | 评测协议设计、向量模型选型、重排 A/B 的实验方法 | 前端与本地化 |

---

## 3. 改造纪律

### 3.1 六步闭环

每一项改动都必须走完这六步，缺一项就不算完成：

```
症状 → 证据 → 根因 → 修复 → 量化 → 回归测试
```

"加一个功能"不是立项理由；"发现某处配置写了但没生效，量化影响，修掉并加测试"才是。

### 3.2 三条红线

1. **不破坏上游行为**：所有改动保留回退路径（`KH_UI_LANGUAGE=en` / `PDF_OCR_ENABLED=false` / 新开关默认关）。
2. **密钥永不入库**：`.env`、`ktem_app_data/`、任何 provider spec 都不进 git。
3. **数字必须能复现**：任何写进简历的数字，都要能指向一条命令和一份结果文件。

### 3.3 每项开工前先回答

- 这次要改善**哪个指标**？（Hit@1 / MRR / facts / abstain / token / 延迟）
- 改动前是多少？用哪条命令测的？
- 如果没改善，结论是什么？（"没改善"也是一个有效结论，但要能解释为什么）

---

## 4. A 组：让成果被看见、被验证

> 目标：任何人 5 分钟内能判断这个项目做了什么、做得怎么样。**优先级最高，因为它决定别人会不会往下看。**
> 合计约 1.5–2 天。

### A1 提交历史重构 + 自有远程仓库（0.5 天）

**现状**：21 个已跟踪文件改动全部未提交，`HEAD` 是上游 commit `9ad3e4e`（`feat: integrate PaddleOCR …`，2026-05-30）。

**做法**

1. 按语义拆成 9 个 commit（顺序即提交顺序；需要时用 `git add -p` 只暂存部分 hunk，一个 commit 里混了两件事就在 message 正文说明）：

| # | commit message | 主要文件 |
|---|---|---|
| 1 | `chore: ignore runtime caches` | `.gitignore` |
| 2 | `chore(deps): add OCR / docx / localization deps` | `libs/kotaemon/pyproject.toml`、`libs/ktem/pyproject.toml`（顺手给 `rapidocr-onnxruntime` 补上界） |
| 3 | `fix(retrieval): default scope was not a valid choice, retrieval silently returned nothing` | `utils/selector.py`(新)、`index/file/ui.py`、`index/file/index.py`、`index/file/graph/*.py`(3)、`ktem_tests/test_file_selector.py`(新) |
| 4 | `feat(loaders): per-page OCR for scanned PDFs` | `loaders/ocr_pdf_loader.py`(新)、`loaders/__init__.py`、`indices/ingests/files.py`、`tests/test_ocr_pdf_reader.py`(新) |
| 5 | `feat(i18n): collect → translate → cache → write-back pipeline` | `utils/i18n.py`(新)、`assets/i18n/zh.json`(新)、`ktem_tests/test_i18n.py`(新)、`app.py`、`ktem/app.py`、`assets/js/main.js`、`pages/help.py`、`mcp/ui.py`、`utils/render.py`、`docs/*.zh.md` |
| 6 | `feat(embeddings): DashScope text-embedding-v3, E5 prefixes, batching` | `flowsettings.py`、`embeddings/fastembed.py`、`embeddings/openai.py`、`.env.example` |
| 7 | `feat(chat): tell the user when nothing is retrievable` | `pages/chat/__init__.py` |
| 8 | `docs+tooling: README.md, MODIFICATIONS.md, eval & reindex tools` | `README.md`、`MODIFICATIONS.md`、`tools/` |
| 9 | `chore(deps): refresh uv.lock` | `uv.lock`（单列，约 9000 行改动，说明是 workspace 依赖变化） |

2. **保留 fork 关系**（推荐）：推送到自己的 GitHub 仓库，README 顶部写明"在 kotaemon v0.12.0 基础上新增 N 个 commit、`+412 −61` 行"（补依赖上界后会有一两行浮动，以最终 `git diff --stat` 为准）。保留 fork 关系更诚实，也方便对比上游。
   - 备选：orphan 分支（把上游压成 1 个 `vendor:` commit），历史干净但失去 fork 关系。**不推荐**——"基于开源项目二次开发"本身是加分项，藏起来反而解释不清。
3. 同步修正 `MODIFICATIONS.md` §1 的统计口径（现写 `+395 −59`，实际已是 `+412 −61`）。
4. 发布前审计：

```powershell
# 1) 已跟踪内容里不应出现真实密钥
#    当前实测命中 10 行，全部是 .env.example / README / docs 里的占位符（如 <YOUR_OPENAI_KEY>）——属预期
git grep -nE "sk-[A-Za-z0-9]{16,}|API_KEY=\S+" -- .
# 2) 敏感路径不应被跟踪（应当没有任何输出）
git ls-files | Select-String "^\.env$|ktem_app_data|sql\.db|fastembed_cache"
# 3) 工作区的 .env 必须处于被忽略状态（应打印命中的 .gitignore 规则）
git check-ignore -v .env
```

**验收**：`git log --oneline -9` 每行可读、不出现"wip/update"；仓库首页有中文 README 与指标表；上面两条审计命令结果符合预期。

### A2 CI 纳入 `ktem_tests` + 新模块覆盖率（0.5 天）

**现状**：上游 CI 只跑 `libs/kotaemon`，而且 matrix 只有 ubuntu；`test_qa.py` 因 `from index import …` 无法收集。

**做法**：新增 `.github/workflows/app-tests.yaml`：

```yaml
name: app-tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    env: { THEFLOW_TEMP_PATH: ./tmp }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --python 3.10 --no-install-package llama-cpp-python
      - run: >
          .venv/bin/python -m pytest
          libs/ktem/ktem_tests libs/kotaemon/tests/test_ocr_pdf_reader.py
          -q --ignore=libs/ktem/ktem_tests/test_qa.py
      - run: >
          .venv/bin/coverage run --source=libs/ktem/ktem/utils,libs/kotaemon/kotaemon/loaders
          -m pytest libs/ktem/ktem_tests -q --ignore=libs/ktem/ktem_tests/test_qa.py
      - run: .venv/bin/coverage report --include="*/i18n.py,*/selector.py,*/ocr_pdf_loader.py"
```

要点：
- `--no-install-package llama-cpp-python`：Linux 上它会走源码编译，CI 里没有必要；
- `rapidocr`/`cv2` 在 `ocr_pdf_loader` 里是**函数内惰性导入**，测试用 stub 替换引擎，所以 CI 不需要 `libgl1`；一旦新增会真正调用 OCR 的测试，就要补 `sudo apt-get install -y libgl1 libglib2.0-0`（或把 `opencv-python` 换成 `headless`）。
- 覆盖率只报**新增模块**（`i18n.py` / `selector.py` / `ocr_pdf_loader.py`），全仓库覆盖率长期在 5% 量级，报它没有意义。

**验收**：Actions 绿色；badge 进 README；三个新模块覆盖率 ≥80%；本地跑同一组命令结果一致。

### A3 一键启动脚本（0.25 天；Docker 可选，0.5–1 天）

**现状**：`scripts/run_windows.bat` 是完整离线安装器（下载 Miniconda、便携 Git），不适合本仓库的 `uv` 工作流；`uv sync` 必须带 `--no-install-package llama-cpp-python`（Windows 无轮子），这是新手第一个坑。

**做法**：新增 `scripts/bootstrap_windows.ps1`（纯 ASCII，避免 PowerShell 5.1 用 GBK 解析中文）：

1. 检查 Python 3.10（`uv python find 3.10`，没有则 `uv python install 3.10`）；
2. `uv sync --python 3.10 --no-install-package llama-cpp-python`；
3. `.env` 不存在才从 `.env.example` 复制（绝不覆盖）；
4. 设置 `TMP`/`TEMP`/`THEFLOW_TEMP_PATH` 后启动 `app.py`。

**Docker 降级为可选**：本机 Docker CLI 29.6.2 有、daemon 未启动，无法验证 build，写"已支持 Docker"会变成又一个未验证的声明。若要补，需要：`libgl1`、`libglib2.0-0`、`libmagic1`，并把 `pip install llama-cpp-python` 排除掉。

**验收**：全新目录（或用 `git clone` 到临时路径）按脚本一次起到登录页；脚本重复执行不破坏已有 `.env`。

### A4 演示素材（0.5 天）

四组对比图，放 `docs/images/zh/`（`docs/images/` 已存在，是上游英文截图）：

| 图 | 内容 | 说明什么 |
|---|---|---|
| 1 | 英文界面 vs 中文界面 | 本地化效果（同一页面同一位置） |
| 2 | 扫描件"答不出 / 引用 `No evidence found.`" vs 修复后"答案 + `[第 2 页]`" | 数据入口缺陷的真实影响 |
| 3 | 评测结果表（含逐题明细） | 有量化，而不是"感觉不错" |
| 4 | 索引块导出：`Page thumbnail` + 37–59 字符标题块 vs 2322 字符正文块 | 定位过程可复现 |

**验收**：README 首屏 3 屏内能看到图 1 与图 3；图片总大小 <3 MB。

### A5 数字自证表（0.25 天）

在 `README.md` 末尾加一张表，把每个对外数字钉到命令与结果文件：

| 数字 | 命令 | 结果 |
|---|---|---|
| Hit@1 59.3% / MRR 0.702 | `python tools/eval_retrieval.py --eval tools/eval/zh-points-rules.json --out tools/eval/results.md --json tools/eval/results.json` | `tools/eval/results.json` |
| 88 passed | `pytest libs/ktem/ktem_tests libs/kotaemon/tests/test_ocr_pdf_reader.py -q --ignore=libs/ktem/ktem_tests/test_qa.py` | 终端输出 / CI |
| 正文 209 → 2322 字符 | `python tools/reindex_corpus.py --match 积分细则` 后读 Source.note | 数据库 `ktem_app_data/user_data/sql.db` |
| 336 条词条 | `python -m ktem.utils.i18n stats --language zh` | 终端输出 |

**验收**：逐条在本机跑通；表里不出现任何无法复现的数字。

---

## 5. B 组：深度闭环

> 目标：把"我发现并修复了问题"升级为"我能证明每一步改动带来了多少收益"。
> **先做 B1**，因为其余各项都要用它当尺子。选 2–3 项做透，合计 3–4 天。

### B1 评测协议升级（1–1.5 天，最高杠杆）

**现状**：2 文件 / 8 块 / 27 题。检索器默认取 `num_retrieval=10` 个块、事实核验窗口是 top-5，而库里总共只有 8 个块（4 目标 + 4 干扰），命中名额被摊薄——单文件（4 块）时 Hit@5 = 100%、MRR 0.739；加入第二个文件后 Hit@5 → 81.5%、MRR → 0.702，Hit@1 基本不变。**这个量级的语料测不出重排是否有效。**

**做法**

1. **语料扩到 10–12 篇公开文档**，放 `tools/eval/corpus/`（总大小 <20 MB，可自由分发：公开政策文件、学校/政府公示 PDF、Python 官方文档章节），其中至少 1 篇扫描件（验证 OCR 链路）、1 篇 docx（验证本地读取器）、2 篇与问题无关的干扰文档。
2. **题目 120 条，四类分层**：

| 类别 | 数量 | 例子 | 测什么 |
|---|---|---|---|
| T1 单跳定位 | 40 | 这份细则的满分是多少分 | 基础召回 |
| T2 细节数值 | 30 | 英语四级加几分、六级加几分 | 块粒度是否够细 |
| T3 跨文档/多跳 | 20 | 奖学金截止日期与积分公示时间是否冲突 | 多路召回与融合 |
| T4 无答案 | 30 | 知识库里根本没有的问题 | 拒答与幻觉 |

3. **指标按类别拆分**：Hit@1/@3/@5、MRR、facts 各自带 T1/T2/T3，T4 单独报 abstain（"正确地说不知道"的比例）。
4. `tools/eval_retrieval.py` 增加 `--category`（只跑某类）与 `--top-k`，报告里按类别分行。
5. 一页 `tools/eval/README.md` 写清：语料从哪来、许可、如何一键装载（`--drop` 重建）、如何加题。
6. **修掉退出码语义**：现在的实现是 `return 0 if hit_at_1 == 1.0 else 1`（`eval_retrieval.py:359`），只要没到 100% 就返回 1，无法直接进 CI。改成 `--fail-under-hit1 0.55` 之类的阈值参数，默认不拦。

**验收**：n ≥ 100；报告含分类指标；把仓库 clone 到新目录、按 `tools/eval/README.md` 的步骤能复现出同一组数字（±0 完全一致，因为不涉及模型随机性）。

### B2 重排闭环（1 天）

**现状**：`rerankers` 在 `kotaemon/indices/vectorindex.py:240` 执行，默认 Cohere 无 key → 原样返回（检索后只有一行日志提示）。

**做法**（三选一，按优先级）

| 方案 | 实现 | 代价 | 备注 |
|---|---|---|---|
| 本地 ONNX cross-encoder（**推荐**） | 升级 `fastembed>=0.5` 用 `TextCrossEncoder`（`Xenova/ms-marco-MiniLM-L-6-v2`，约 90 MB，CPU，无 torch） | 新增 1 个依赖升级 + 模型下载 | 现装 fastembed 0.4.2 **没有** cross-encoder API，必须先升级 |
| 自实现 ONNX 打分 | 用已装的 `onnxruntime 1.19.2` + `transformers 4.56.2` tokenizer 直接跑 | 约 80 行代码，无新依赖 | 升级 fastembed 有风险时的退路 |
| 通义 `gte-rerank`（对照） | 新增 `BaseReranking` 子类，直接打 DashScope HTTP | 需要额度与网络 | 只作对照，不作为默认 |

实现要点：新增 `libs/kotaemon/kotaemon/rerankings/local_onnx.py`；`flowsettings.py` 注册；`tools/eval_retrieval.py` 加 `--rerank on|off` 做 A/B；失败必须回退为"不重排"而不是报错。

**验收**：同一套 B1 评测下给出 `--rerank on/off` 的 Hit@1、MRR、facts 对比，**并给出 P50/P95 延迟**。若没有提升，写清原因（模型语言不匹配 / 块粒度太粗 / 召回阶段就把正确答案丢了），这也是有效结论。

### B3 切块粒度 A/B（0.5 天）

**现状**：索引 `chunk_size=0` → 按页成块（每页约 500–650 字）。

**做法**：通过 `flowsettings.FILE_INDEX_PIPELINE_SPLITTER_CHUNK_SIZE` / `CHUNK_OVERLAP`（`pipelines.py:68-76` 会读）改成 512/64，确认切块后 `page_label` / `file_name` 元数据仍被继承（引用面板依赖它），重建索引后跑 B1 评测。

**验收**：块数从 8 级涨到 ~60 级；Hit@1 与 facts 的前后对比；报告里明确"块变多、top_k 不变"带来的副作用（噪声块增加）。

### B4 拒答闸门（0.5–1 天）

**现状**：没有可检索文件时会给出提示（已修），但"检索到了不相关的内容"仍会硬答。

**做法**：在回答前加一道判断——检索最高分低于阈值（用 B1 的 T4 校准，不要拍脑袋），或关键事实缺失时，明确输出"知识库中没有找到依据"，并给出下一步建议（换关键词 / 换文件 / 扩大检索范围）；同时记录被拦截的查询。

**验收**：T4 拒答率 ≥90%，T1–T3 误拒 ≤5%；拦截记录可导出。

### B5 `doctor` 自检命令（0.5 天）

**动机**：这个项目已经出现过三次"配置写了但功能静默失效"。把它做成一条命令，比再写三段文字更有说服力。

**做法**：`tools/doctor.py`（或 `python -m ktem.utils.diagnostics`）检查并输出表格：

1. 每个 Source 的 `note.loader` / `tokens` / 块数，标出 `tokens` 缺失或块数为 0 的文件；
2. 空文本块比例；
3. 检索 smoke：3 个固定问题，召回是否非空、命中页码；
4. 配置生效：embedding provider 与维度、reranker 是否有 key、词表是否加载（条数）、`PDF_OCR_ENABLED`；
5. 任一异常返回非零退出码，可直接进 CI。

**验收**：故意删掉一个 Source 的索引块、或把 reranker 换成无 key 的 provider，doctor 必须报警并给出修复建议。

---

## 6. C 组：加分项（1 天/项，按需）

### C1 端到端评测
`tools/eval_end2end.py`：答案关键事实命中率、**引用页码正确率**（答案里的 `[第 N 页]` 必须属于送入模型的块的页码集合）、平均 token、P50 延迟。用 DeepSeek 跑 120 题，成本在几毛钱量级。需处理限流与 402（余额）错误：失败重试 3 次后跳过并记录，不静默计为通过。

### C2 多轮追问改写
框架里有 `RewriteQuestionPipeline`，但 `use_rewrite` 只绑定在 `regen` 状态上（`libs/ktem/ktem/reasoning/simple.py:389`），多轮历史从未进入改写。做法：把 `history` 传入改写管线、新增开关（默认开但可关）、补一套 20 条的多轮评测集（第二轮问题是否还能命中）。验收：多轮 Hit@1 前后对比。

### C3 成本与延迟
`use_llm_reranking` 默认开启，每次回答会额外对每个召回块调一次 LLM 打分（`simple.py:297-304`）。做法：量化开/关的 token 与延迟差，再决定是否用 B2 的本地分数替代它（引用面板的分数显示需要保留）。验收：每题平均 token、P50 延迟的前后对比。

### C4 查询 trace
把每次查询的召回数、重排前后名次、各阶段耗时、token 落成 jsonl，附带一个聚合小脚本。价值在于"能解释一次回答为什么是这样"，也是面试里"你怎么排查线上问题"的答案。

### C5 更多本地读取器
`.pptx` / `.xls` / `.doc` 仍走 `unstructured`（同样的 `libmagic` + 403 风险），按 `.docx` 的方式逐个替换为本地读取器，每个格式配 1 个测试。延续"同类缺陷"的叙事。

---

## 7. D 组：明确不做

| 不做 | 理由 |
|---|---|
| 微调模型 | 与项目定位（应用改造）不符，讲不出比"用评测选型"更好的故事 |
| 多租户 / 权限体系 | 属于另一个项目，与本项目的主线无关 |
| 自研向量库 / 索引结构 | 无法在有限时间内做到能与 Chroma/LanceDB 对比的水平 |
| K8s / 生产部署 | 本地项目无法验证，写进去就是空话 |

> **2026-10-18 更新：原"重写前端 / 换 UI 框架：明确不做"已被推翻。**
> 改做第二代前端（React SPA + FastAPI，Gradio 退居 `/legacy`），原因与实现见
> [MODIFICATIONS §5.25](MODIFICATIONS.md#525-第二代前端react-spa--fastapi2026-10-18)。
> 原先的两条顾虑仍然成立，因此方案按此设计：**本地化层与测试留在 Python 侧不重写**，
> 新 UI 复用同一套服务与词表；分阶段迁移，每阶段可回滚（`KH_WEB_UI=0`）。
>
> **2026-10-19：M3 完成。** 资源（索引/模型只读视图 + 用户管理）、帮助、账户改密已在新界面，
> 见 [MODIFICATIONS §5.28](MODIFICATIONS.md#528-m3资源帮助与账户页面2026-10-19)；
> 剩下的只有 M4（把供应商编辑表单迁完并下线 Gradio 默认入口）。

---

## 8. 推荐路线

### 8.1 三档时间预算

| 档位 | 内容 | 得到什么 |
|---|---|---|
| **1 天（发布版）** | A1 + A2 + A5 | 已经能挂上简历：数字不多但每条都可复现，历史与 CI 干净 |
| **3–4 天（MVP 简历版，推荐）** | 上面 + B1 +（B2 或 B5） | 有"评测驱动优化"的完整闭环——这是最能讲的一条 |
| **1.5 周（完整版）** | 上面 + B3 + B4 + C1 + C3 | 指标、成本、延迟三条曲线齐全，可讲"工程权衡" |

### 8.2 依赖顺序

```
A1 ──> A2 ──>（CI 绿色）
 └───> A4 ──> A5
B1 ──> B2 ──> B3 ──> B4      （评测是尺子，必须先有）
 └───> C1
B5 可独立并行
```

### 8.3 注意事项

- 跑测试 / 评测 / 重建索引前**先停掉应用**（共用 sqlite 与 LanceDB，冲突会静默长时间挂起）；
- 换向量模型或改切块后**必须重建索引**（维度不同 / 块变了），用 `tools/reindex_corpus.py`；
- `IndexDocumentPipeline.stream()` 会吞异常，重建后必须检查 `channel == "index"` 的返回内容，不能只看退出码；
- 造题（B1）占掉该项 70% 的工作量，不要低估。

---

## 9. 简历与面试映射

> 本节与前几节内容完全独立。若仓库公开，可以把本节移到本地笔记——技术部分不依赖它。

### 9.1 一句话定位

现状版：

> 在开源 RAG 框架 kotaemon 上完成中文产品化改造：接入 DeepSeek + 通义向量实现零本地模型成本的知识库问答；定位并修复三类"配置生效但功能静默失效"的数据入口缺陷（召回为空 / 扫描件无正文 / docx 未入库）；在框架无 i18n 机制的前提下实现译文本体外置的本地化流水线（336 词条）。

完成后版（`<>` 待填真实数字）：

> …建立 120 题分层检索评测作为优化尺子，Hit@1 从 36.7% 提升到 <>%，并在同一套评测下量化了重排与切块的收益。

### 9.2 三条 bullet（模板）

1. **缺陷定位**：从"引用栏为空但模型仍能作答"出发，定位到选择器默认值非法 + 全库检索依赖陈旧 UI 状态两处叠加缺陷，覆盖 File 索引与 3 个 GraphRAG 分支；抽成纯函数并补 10 个不变量用例。
2. **数据入口**：扫描件正文未入库（209 字符/4 页，全是标题）+ docx 索引静默失败；实现按页决策的 OCR 抽取器与本地 docx 读取器，同一文件正文恢复到 2322 字符，答案带页码引用。
3. **评测驱动**：自建只跑检索层、零 token 成本的评测（<> 题、<> 篇文档、四类分层），用它把向量模型从 Hit@1 36.7% 换到 <>%，并量化重排/切块的收益与延迟代价。

### 9.3 指标表（现状 → 目标）

| 指标 | 现状 | 目标（B 组完成后） |
|---|---|---|
| 评测规模 | 27 题 / 8 块 | ≥120 题 / ≥100 块 / 10+ 文档 |
| Hit@1 | 59.3% | 待测（重排 + 细粒度切块后） |
| MRR | 0.702 | 待测 |
| 无答案集拒答率 | 未测 | ≥90% |
| 答案级准确率 | 未测 | 待测（C1） |
| 每题 token / P50 延迟 | 未测 | 待测（C3） |

> 原则：**已测的写实测值，未测的写"未测"，不写估计值。** 面试官追问"这个数字怎么来的"，答"没测"远好过答"大概"。

### 9.4 面试 Q&A（答法骨架）

| 问题 | 要点 |
|---|---|
| 这是 fork，哪部分是你写的？ | 报 commit 数、改动行数、文件清单；强调"定位宿主框架缺陷"部分是自己做的；主动说清哪部分是上游已有的 |
| Hit@1 60% 算好吗？ | 先给口径（27 题、8 块、页码级判定），再给天花板效应（单文件 Hit@5=100%，n 太小），再说 B1 要扩到多大 |
| 为什么不上重排/微调？ | 重排有配置但没 key，属于"假生效"；先用评测证明值得再改。微调不在定位内 |
| 评测集是你自己造的，会过拟合吗？ | 承认风险；四类分层 + 无答案集 + 保留一部分题只在最终报告时跑 |
| 为什么用通义而不是本地模型？ | 同一套评测：通义 v3 60.0%/0.736，本地 mpnet 60.0%/0.739（30 题口径），指标相当；通义省 1 GB 本地模型，本地模型作离线兜底 |
| 三处静默失效怎么发现的？ | 讲证据链：引用栏空 → 导出索引块 → 看 `note` 与块内容 → 排除算法、锁定数据入口 |
| 改成这样能上生产吗？ | 说清缺什么：鉴权粒度、并发、限流、监控、密钥托管；不吹 |
| 如果给 10 倍数据会怎么变？ | 向量库选型、切块策略、重排必要性、评测成本——这题考的是有没有想过规模 |

### 9.5 发布决策

- 保留 fork 关系（`Forked from Cinnamon/kotaemon`），README 顶部一句话说明改造范围；
- 许可证是 **Apache-2.0**（`LICENSE.txt`，仓库无 `NOTICE` 文件）：保留原文件、新增文件不追加其它许可，并在 README 写明"已修改上游文件"——Apache-2.0 §4(b) 要求标注被修改的文件，用 commit + README 说明可追溯即可，不必逐文件加文件头；
- 若不想公开 §9，移动后再推送。

---

## 10. 发布前检查清单（DoD）

- [ ] `git log --oneline -9` 每行可读，无 `wip/update/fix` 之类
- [ ] `git grep` 审计无真实 key；`.env`、`ktem_app_data/`、`*.db` 均未跟踪
- [ ] `LICENSE.txt` 保留（Apache-2.0）；README 顶部写明与上游的关系以及"本文档以外均为修改"
- [ ] CI 绿色 + badge 进 README
- [ ] README 首屏有截图与指标表；指标表里每个数字都能在 A5 表里找到命令
- [ ] 文档链接与锚点全部可用（`MODIFICATIONS.md#...`、`tools/eval/README.md`）
- [ ] 全新环境按一键启动脚本能起到登录页
- [ ] 停掉应用后，测试与评测命令各跑通一次
- [ ] 内部文档已脱敏：机构名、文件名、专有信息不出现在任何将要推送的文件里（评测集里用 `--corpus` 覆盖真名）
- [ ] 截图只拍聊天页与文件列表页，不拍 provider 配置页
- [ ] 临时文件、实验脚本没有残留在仓库里（`tools/__pycache__` 等）
- [ ] 简历里出现的每个数字，都能在 30 秒内演示其复现命令

---

## 附录 A：命令速查

```powershell
# 启动（先停掉占用 sqlite/LanceDB 的其它进程）
$env:TMP="$PWD\ktem_app_data\tmp"; $env:TEMP=$env:TMP
$env:THEFLOW_TEMP_PATH="flow_tmp"; $env:KH_UI_LANGUAGE="zh"
.\.venv\Scripts\python.exe -X utf8 app.py

# 测试（离线，需先停应用）
.\.venv\Scripts\python.exe -m pytest libs/kotaemon/tests/test_ocr_pdf_reader.py `
    libs/ktem/ktem_tests -q --ignore=libs/ktem/ktem_tests/test_qa.py

# 检索评测
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json `
    --out tools\eval\results.md --json tools\eval\results.json

# 重建索引（换向量模型 / 改切块后必须做）
.\.venv\Scripts\python.exe tools\reindex_corpus.py --drop
.\.venv\Scripts\python.exe tools\reindex_corpus.py --match "积分细则"

# 词表统计 / 同步进仓库
.\.venv\Scripts\python.exe -m ktem.utils.i18n stats  --language zh
.\.venv\Scripts\python.exe -m ktem.utils.i18n bundle --language zh
```

## 附录 B：口径说明

| 术语 | 定义 |
|---|---|
| Hit@k | 期望页码是否出现在前 k 个检索块里 |
| MRR | 第一个命中块名次的倒数（排第 1 得 1.0，排第 4 得 0.25） |
| facts（关键事实覆盖） | 期望事实是否出现在送给模型的文本里，能抓"页对了但块不对" |
| abstain | 无答案问题上正确回答"知识库中没有"的比例 |
| 静默失效 | 配置/开关显示已生效，实际代码路径被短路或异常被吞，界面无报错 |
