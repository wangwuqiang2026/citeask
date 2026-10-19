## 1. 登录

打开 <http://127.0.0.1:7860>，默认账号 `admin` / `admin`。
登录使用 HttpOnly Cookie（`ktem_session`），刷新页面不会丢；「设置」页顶部可以改自己的密码。
需要回滚到经典界面时，在 `.env` 里设 `KH_WEB_UI=0` 并重启，根路径会回到 Gradio，经典界面始终在 `/legacy/`。

## 2. 先配模型

至少配置一个对话模型和一个向量模型：

1. 进入「资源」页，选「模型资源」。
2. LLM 分组点「新增」，例如 `ChatOpenAI`，填 `api_key`、`model`，可设为默认。
3. 向量分组点「新增」，选通义或本地 FastEmbed；不配通义 key 时默认走本地。
4. 重排与 MCP 也在同一页；表单字段由服务端供应商类的 `describe()` 生成。
5. 非管理员只能看列表，改配置需要管理员；列表接口不会返回 `spec`（里面有 API key）。

## 3. 添加文件

进入「文件」页：

- **上传**：拖入或选择文件，支持 PDF / DOCX / PPTX / XLSX / XLS / TXT 等；
  进度通过 SSE 实时显示，完成后出现在文件表。
- **URL 导入**：粘贴可访问的文档 URL。
- **分组**：新建分组后可以把文件拖进去，提问时按分组筛选。
- **文件表**：查看分块、下载、重建索引、删除；解析失败会显示原因，不会留下"幽灵文件"。
- 扫描版 PDF 会在索引时按页 OCR；OCR 失败会保留原文字层，不会把页面变空。

## 4. 提问与引用

1. 在聊天框输入问题，`@` 选择文件，`Ctrl/⌘+Enter` 发送。
2. 回答流式返回；引用标记（上标数字，底层是 `【n】`）可点击，右侧证据抽屉会定位到文件、页码、片段和分数。
3. 证据抽屉里可以搜索、看相关性条、打开原文（`/legacy/file=...#page=N`）。
4. 没有可靠依据时，拒答闸门会直接说"知识库中没有回答这个问题所需的依据"，而不是让模型凭记忆编。
5. 新建对话会自动命名；顶部可以切换模型、语言、引用策略和简单/复杂问答模式。

## 5. 设置

「设置」页是 schema 驱动的表单：文件集合、推理、简单问答、复杂问答、ReAct、ReWOo 分组，
每项都有类型、默认值与说明；保存是吸底的，未保存时离开会提示。账户改密在页面顶部。

常用环境变量：

| 变量 | 作用 |
|---|---|
| `KH_APP_DATA_DIR` | 数据根目录（文档、SQLite、LanceDB、模型缓存、会话密钥）；演示/测试时指向独立目录 |
| `KH_WEB_UI` | `1` 用 React SPA；`0` 回滚到经典 Gradio |
| `KH_UI_LANGUAGE` / `KH_ANSWER_LANGUAGE` | 界面语言 / 回答语言 |
| `PDF_OCR_ENABLED` / `PDF_OCR_MIN_CHARS` / `PDF_OCR_DPI` | 扫描页 OCR 开关、阈值与渲染精度 |
| `KH_ABSTAIN_SCORE_THRESHOLD` | 拒答阈值，`0` 关闭 |

## 6. 快捷键

- `Ctrl/⌘+K`：命令面板（跳转页面、新建对话）。
- `Ctrl/⌘+Enter`：发送。
- `Shift+Enter`：换行。
- `Esc`：关闭弹层 / 证据抽屉。

## 7. 给开发者

- API 前缀 `/api/v1`，共 39 个接口；会话 Cookie 为 HMAC 签名的 HttpOnly Cookie。
- 路由只做鉴权/序列化，业务在 `ktem/services/*`，不 import gradio，可脱离 UI 单测。
- 评测：`python tools/eval_retrieval.py --eval tools/eval/fixture-points.json`（公开 9 题）；
  私有 27 题用 `--corpus` 指向自己的语料。
- 自检：`python tools/doctor.py`；索引重建：`python tools/reindex_corpus.py`。
