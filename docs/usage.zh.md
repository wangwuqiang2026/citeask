## 1. 添加你的 AI 模型

![resources tab](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/resources-tab.png)

- 本工具使用大语言模型（LLM）完成问答流程中的各类任务，因此需要先让应用能访问你要使用的 LLM。
- 至少配置一个即可。不过建议把你手头可用的 LLM 都配上，这样在使用过程中可以随时切换。

添加模型的方法：

1. 进入 `资源` 页。
2. 选择 `LLM` 子页。
3. 选择 `添加` 子页。
4. 配置要添加的模型：
   - 给它起一个名字。
   - 选择供应方（例如 `ChatOpenAI`）。
   - 填写参数规格。
   - （可选）把它设为默认模型。
5. 点击 `添加`。
6. 切到 `向量模型` 子页，重复第 3–5 步添加一个向量模型。

<details markdown>

<summary>（可选）通过 .env 文件配置模型</summary>

你也可以通过 `.env` 文件来配置模型，把连接 LLM 所需的信息写进去。该文件位于应用所在目录；
如果没有，可以自己新建一个。

目前支持以下供应方：

### OpenAI

在 `.env` 文件中设置 `OPENAI_API_KEY` 为你自己的 OpenAI API key，即可启用 OpenAI 的模型。
其他变量也可以按需调整，不改的话默认参数对大多数人来说都能正常工作。

```shell
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=<在此填入你的 OpenAI API key>
OPENAI_CHAT_MODEL=gpt-3.5-turbo
OPENAI_EMBEDDINGS_MODEL=text-embedding-ada-002
```

### Azure OpenAI

若要通过 Azure 平台调用 OpenAI 模型，需要提供 Azure 的 endpoint 与 API key。
根据你的 Azure 配置方式，可能还需要提供对话模型与向量模型的部署名。

```shell
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
OPENAI_API_VERSION=2024-02-15-preview # 你的值可能不同
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-35-turbo # 改成你的部署名
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002 # 改成你的部署名
```

### 本地模型

优点：

- 隐私：文档的存储与处理都在本地完成。
- 选择多：可按体量、领域、语言挑到各种不同的 LLM。
- 成本：免费。

缺点：

- 效果：本地模型体量小得多，生成质量通常低于付费 API。
- 速度：本地模型跑在你的机器上，处理速度受硬件限制。

#### 寻找并下载模型

你可以在 [Hugging Face Hub](https://huggingface.co/models) 上搜索并下载本地运行的 LLM。
目前支持以下模型格式：

- GGUF

请选择体量小于你设备内存的模型，并预留约 2 GB 余量。例如总共 16 GB 内存、可用 12 GB，
那么模型最多占 10 GB。模型越大生成效果通常越好，但耗时也更长。

以下是一些推荐及其内存占用：

- [Qwen1.5-1.8B-Chat-GGUF](https://huggingface.co/Qwen/Qwen1.5-1.8B-Chat-GGUF/resolve/main/qwen1_5-1_8b-chat-q8_0.gguf?download=true)：
  约 2 GB

#### 启用本地模型

要把本地模型加入模型池，请在 `.env` 文件中把 `LOCAL_MODEL` 设为模型文件的路径。

```shell
LOCAL_MODEL=<你的模型文件完整路径>
```

获取模型文件完整路径的方法：

- Windows 11：右键该文件，选择 `复制文件地址`。
</details>

## 2. 上传你的文档

![file index tab](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/file-index-tab.png)

要对文档做问答，需要先把它们上传到应用中。进入 `文件集合` 页，你会看到两个区域：

1. 文件上传：
   - 把文件拖拽到界面，或从文件系统中选择文件，然后点击 `上传并建立索引`。
   - 应用处理文件需要一些时间，完成后会给出提示。
2. 文件列表：
   - 这里显示已上传到应用的文件，并允许删除它们。

## 3. 与你的文档对话

![chat tab](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/chat-tab.png)

现在回到 `对话` 页。该页分为三个区域：

1. 会话设置面板
   - 在这里可以新建、重命名、删除和切换会话。
     - 默认情况下，如果没有选中任何会话，会自动新建一个。
   - 下方是文件索引选择器，可以决定是禁用检索、检索全部文件，还是只检索指定文件。
     - 选择「禁用」时，对话不会把任何文件作为上下文。
     - 选择「检索全部」时，所有文件都会参与对话。
     - 选择「指定文件」时会出现一个下拉框，用于挑选参与对话的文件；
       若没有勾选任何文件，则不会有文件参与对话。
2. 对话面板
   - 在这里与助手对话。
3. 信息面板

![information panel](https://raw.githubusercontent.com/Cinnamon/kotaemon/develop/docs/images/info-panel-scores.png)

- 这里会显示召回的证据与引用等辅助信息。
- 回答中直接引用的部分会被高亮标出。
- 同时显示回答的置信度与各条证据的相关度得分，便于快速判断回答与召回内容的质量。

- 各得分的含义：
  - **答案置信度**：LLM 给出的回答置信程度。
  - **相关度得分（Relevance score）**：证据与用户问题之间的总体相关度。
  - **向量库得分（Vectorstore score）**：由向量嵌入相似度计算得到
    （若来自全文检索数据库，则显示 `full-text search`）。
  - **LLM 相关度得分**：由 LLM 通过特定提示词判断题干与证据相关性所得的分数。
  - **重排序得分（Reranking score）**：由 Cohere [重排序模型](https://cohere.com/rerank) 给出的分数。

一般来说，得分的可信程度依次为 `LLM 相关度得分` > `重排序得分` > `向量库得分`。
默认情况下，总体相关度直接取自 LLM 相关度得分；证据按其总体相关度以及是否带有引用进行排序。
