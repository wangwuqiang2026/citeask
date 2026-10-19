# 关于 citeask

citeask 是一个面向中文文档的知识库问答应用：**扫描件与长文档可以直接入索引，回答带页码引用，
检索效果用一套只跑检索层的评测驱动迭代。**

## 能做什么

- **扫描件也能查**：PDF 文字层不足 200 字符时按页渲染并走本地 OCR（PP-OCR），失败保留原文字层。
- **逐页可溯源**：回答里的 `【n】` 对应证据抽屉中的文件、页码、片段和相关性分数，点开可看原文。
- **文件集合**：原生上传 / URL 导入、分组、分块预览、重建索引、删除；失败会回滚并在列表里显示原因。
- **评测驱动**：`tools/eval_retrieval.py` 只跑检索层、零 token 成本，支持 `--scope`、`--category`、
  `--rerank` 和 Hit@1 门槛。
- **多模型**：对话 DeepSeek；向量默认通义 `text-embedding-v3`，离线可切本地 FastEmbed；
  LLM / 向量 / 重排 / MCP 都能在「资源」页增删改。
- **中文界面**：Gradio 与 React 两套界面都有中文词表，回答语言跟随界面语言。

## 技术栈

React 18 + TypeScript + Vite + Tailwind · FastAPI + SSE · SQLModel/SQLite · LanceDB ·
DeepSeek · 通义 text-embedding-v3 / FastEmbed · PP-OCR (ONNX) · pytest · GitHub Actions。

## 项目主页

- 源码与文档：<https://github.com/wangwuqiang2026/citeask>
- 改造记录与设计取舍：仓库根目录的 `MODIFICATIONS.md`
- 评测说明：`tools/eval/README.md`

## 许可

Apache-2.0。仓库包含 kotaemon 项目的代码（Apache-2.0），上游版权归其作者；
归属说明见仓库根目录的 `NOTICE`，本仓库的修改清单见 `MODIFICATIONS.md`。
