# 检索评测（`tools/eval_retrieval.py`）

只跑**检索层**的评测：不调用任何对话模型，零 token 成本。它衡量的是"答案模型最终看到的
那段文本里，有没有出现该出现的页面和事实"，因此改向量模型、改切块、开/关重排都能用它对比。

为什么要单独有这套东西：项目的每一次优化都必须能回答"哪个指标变了、变了多少"。
没有这套尺子，改动就只是主观判断（见 `ROADMAP.md` §3.3）。

## 先用自带示例语料跑一遍（新 clone 的可复现路径）

仓库提交了一份**虚构内容**的 5 页语料 `fixtures/points-fixture.pptx` 和配套的 9 题
`fixture-points.json`（含 1 道无答案题），不依赖任何私有文件：

```powershell
# 1) 语料已随仓库提交；需要重新生成时（内容确定性、不联网）
.\.venv\Scripts\python.exe tools\eval\make_fixture.py

# 2) 把 fixtures/points-fixture.pptx 上传进「文件集合」，等索引完成（需要向量化：
#    默认通义 text-embedding-v3；离线可用本地 FastEmbed，首次要下模型）

# 3) 跑配套题集（应用需停止，二者共用 sqlite / LanceDB）
.\.venv\Scripts\python.exe -X utf8 tools\eval_retrieval.py --eval tools\eval\fixture-points.json
```

这一步验证的是**评测链路通不通**（语料入库 → 检索 → Hit@k / 拒答统计），
数字本身取决于你用哪个向量模型——`fixture-points.json` 的注释里写了这一点。
题集与语料的一致性有单测兜底：`tools/tests/test_fixture_eval.py` 会检查每个
`expect_pages` 在语料里存在、每个 `expect_terms` 真的出现在对应页、无答案题的词真的
不在语料里——所以题目不会悄悄和语料脱节。

真实语料上的指标见下文；那份语料是私有的（含个人信息），仓库只保留脱敏后的题集，
用 `--corpus "你的文件"` 指向自己的语料即可复现。

## 命令

```powershell
# 应用必须先停掉（评测与它共用 sqlite / LanceDB）
.\.venv\Scripts\python.exe tools\eval_retrieval.py `
    --eval tools\eval\zh-points-rules.json `
    --out tools\eval\results.md `
    --json tools\eval\results.json

# 只跑某一类题（题目带 category 时有效）
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json --category T2

# 限定检索范围（等价界面的「在文件中搜索」）——比较"某份语料本身多好"时必须用
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json --scope "你的语料"

# 重排 A/B：把重排器钉成关 / 开，其余条件不变
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json --rerank off
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json --rerank on

# 拒答闸门：无答案题的拒答率（阈值默认取 KH_ABSTAIN_SCORE_THRESHOLD）
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-no-answer.json --abstain-threshold 0.45

# 当门槛用（Hit@1 低于阈值就返回 1，可进 CI）
.\.venv\Scripts\python.exe tools\eval_retrieval.py --eval tools\eval\zh-points-rules.json --fail-under-hit1 0.55
```

退出码：`0` 完成且（若设了阈值）达标；`1` 设了 `--fail-under-hit1` 但未达标；
`2` 没有可评测的语料 / 指定的类别不存在。**不设阈值时 100% 不是通过条件**——
基线本来就不在 100%（旧实现是 `return 0 if hit_at_1 == 1.0 else 1`，等于永远"失败"）。

## 指标口径

| 指标 | 定义 |
|---|---|
| Hit@k | 期望页码是否出现在前 k 个检索块里 |
| MRR | 第一个命中块名次的倒数（排第 1 得 1.0，排第 4 得 0.25） |
| facts | 期望关键事实是否出现在送给模型的 top-k 文本里（能抓"页对了但块不对"） |
| corpus_chunks | 该语料在检索结果里贡献的块数，也就是 Hit@k 的理论上限 |

## 题目格式（`zh-points-rules.json`）

```json
{
  "name": "评测集名称",
  "corpus": "语料文件名.pdf",
  "questions": [
    {
      "id": "q01",
      "category": "T1",
      "question": "这份细则的满分是多少分？",
      "expect_pages": ["1"],
      "expect_terms": ["满分为100分", "五个部分"]
    }
  ]
}
```

- `expect_pages`：PDF 页码（从 1 开始），与引用面板的 `[第 N 页]` 一致；
- `expect_terms`：命中答案必须能读到的事实片段，匹配前会去掉所有空白（OCR 会在任意位置换行）；
- `category`：可选，用于分组统计。建议的分层（见 `ROADMAP.md` B1）：

| 类别 | 含义 | 测什么 |
|---|---|---|
| T1 | 单跳定位 | 基础召回 |
| T2 | 细节数值 | 块粒度是否够细 |
| T3 | 跨文档 / 多跳 | 多路召回与融合 |
| T4 | 无答案 | 拒答（不硬答） |

没有 `category` 的题统一计入 `未分类`；一个集合里出现 2 个以上类别时，报告才会多出分类表。

## 语料怎么来

- 仓库里的评测集是**脱敏示例**：对象是 `tools/eval/zh-points-rules.json` 里 `corpus` 指定的那份 PDF，
  文件名与机构名已做替换，指标与行为不受影响。
- 换自己的语料：把文件上传进应用、建好索引，然后 `--corpus "你的文件名"` 覆盖 `corpus` 字段即可
  （文件名比较会忽略空白和标点，Gradio 上传时会把 `（2025修订）` 洗成 `2025修订`）。
- 换向量模型或改切块后**必须重建索引**再评测，否则数字没有可比性：

```powershell
.\.venv\Scripts\python.exe tools\reindex_corpus.py --drop            # 换模型：丢库后全量重建
.\.venv\Scripts\python.exe tools\reindex_corpus.py --match "关键词"   # 只重建匹配的文件
```

## 加题的纪律

1. **题目必须能从语料里读出来**，`expect_terms` 用原文片段（去掉空白后做包含匹配）；
2. **不要为某一版实现写题**：题目描述的是语料事实，换了重排/切块后题目不变；
3. **每类题按比例加**：全是 T1 会让 Hit@1 虚高，T4 缺失会让"硬答"永远不可见；
4. **不要估算**：报告里的数字只能来自上面那条命令，不能手填。

## 当前基线（27 题；512/64 切块）

| 检索范围 | 块数 | Hit@1 | Hit@3 | Hit@5 | MRR | 事实覆盖 |
|---|---|---|---|---|---|---|
| 只检索该 PDF（`--scope`） | 11 | **88.9%** | 96.3% | **100%** | **0.933** | **100%** |
| 全库（含 1 万块表格） | — | 77.8% | 85.2% | 88.9% | 0.832 | 81.5% |

历史口径（按页成块，`chunk_size=0`）：单文件 Hit@1 55.6% / MRR 0.707；两文件 8 块 59.3% / 0.702。
切块的 A/B 见 `MODIFICATIONS.md` §5.7。

## 拒答校准集（`zh-no-answer.json`）

12 道"语料里没有答案"的题（校园生活类），用来给拒答闸门定阈值。题目带
`"expect_answer": false`，统计口径是"该拒的拒了没"（abstain 率）与"不该拒的有没有被误拒"
（false reject）。当前阈值 0.45：**abstain 91.7% / 误拒 0%**（`MODIFICATIONS.md` §5.8）。

结果文件：`tools/eval/results.md`（人读）、`tools/eval/results.json`（机读，含
`summary` / `categories` / `abstain` / `results`）。

> 语料只有 4 块时 Hit@5 已接近天花板，这个量级**测不出重排是否有效**（`ROADMAP.md` B1 要扩到
> 10+ 文档 / ≥100 题）。引用这组数字时要把语料规模一起说清楚。
