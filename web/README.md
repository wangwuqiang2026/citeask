# citeask Web UI（React SPA）

M1/M2 阶段的新前端：React 18 + TypeScript + Vite 5 + Tailwind 3.4。构建产物输出到 **`web/dist`**
（已入库），`app.py` 的 FastAPI 宿主优先加载它；旧 Gradio 界面保留在 `/legacy`，可随时回退。

## 1. 目录结构

```
web/
├─ scripts/
│  ├─ vite.inline.mjs    Vite 配置（JS API 内联传入，见 §3）
│  ├─ build.mjs          构建入口（tsc -b → vite build）
│  ├─ dev.mjs            开发服务器（代理 /api /legacy /file= 到 :7860）
│  ├─ preview.mjs        预览已构建的 dist
│  ├─ build_web.ps1      构建 + 可选复制进 Python 包（发布用）
│  └─ sandbox-shim.mjs   Windows 沙箱下绕开 Vite 的 `net use` 调用
├─ src/
│  ├─ main.tsx / App.tsx 入口、路由、登录态、主题、Toaster
│  ├─ index.css          Tailwind + 设计令牌 + Markdown/代码高亮样式
│  ├─ components/
│  │  ├─ app/            AppShell、Rail、命令面板、PageFrame（非聊天页的统一页头/滚动区）
│  │  ├─ chat/           会话侧栏、消息流、Composer、证据抽屉、设置弹层、文件选择
│  │  ├─ files/          文件表、上传弹窗、分块抽屉、分组面板、确认弹窗
│  │  ├─ settings/       schema 驱动的设置控件（text/number/checkbox/dropdown/radio/checkboxgroup）
│  │  └─ ui/             手写 shadcn 风格基元（Button/Input/Dialog/Dropdown/Select/Switch/Tooltip…）
│  ├─ hooks/             react-query 封装、SSE 聊天状态机、媒体查询
│  ├─ lib/               api / SSE 解析 / 引用解析 / i18n / 主题 / 工具 / mock
│  ├─ pages/             ChatPage、LoginPage、FilesPage、SettingsPage、ClassicPage（M3 占位）
│  └─ stores/            zustand：ui（主题/语言/抽屉）、chat-settings（推理/模型/引用…）
├─ dist/                 构建产物（提交入库；index.html + 哈希 assets）
├─ index.html            含首绘前主题脚本（防白闪）
└─ package.json
```

## 2. 命令

```powershell
cd web
$env:npm_config_cache = "D:\Code\VibeCoding\kotaemon\ktem_app_data\tmp\npm-cache"  # 本机必需

npm install --ignore-scripts   # 沙箱里 npm 的 postinstall 会 spawn，见 §3
npm run build                  # tsc -b + Vite → web/dist
npm run preview                # 预览 web/dist（:4173）
npm test                       # Node 内置测试（17 例）
npm run typecheck              # tsc --noEmit
npm run lint                   # ESLint（0 警告）
npm run dev                    # 开发服务器 :5173（需普通环境，见 §3）
```

发布到 Python 包（可选；普通机器）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_web.ps1 -CopyToPackage
```

## 3. 受限 Windows 沙箱下的构建说明

普通终端直接 `npm run build` 即可。本仓库的开发机跑在受限沙箱里，npm 子进程无法使用管道，
因此做了以下**不影响正常环境**的适配，全部在 `scripts/` 内：

| 问题 | 适配 |
|---|---|
| `esbuild` 服务进程 `spawn EPERM` | 构建不用 esbuild/SWC：`@babel/preset-typescript` 去类型、`@babel/preset-react` 编译 JSX、terser 压缩；`esbuild: false` |
| Vite 5 加载**任何**配置文件都会先用 esbuild 打包 | 配置改为 JS 对象（`scripts/vite.inline.mjs`），通过 Vite JS API + `configFile: false` 传入 |
| Vite 在 Windows 上 `exec("net use")` 解析网络盘 | `scripts/sandbox-shim.mjs` 返回空盘符列表（本地盘行为不变） |
| Vite 的 `define` 插件硬依赖 esbuild | `defineWorkaround` 前置替换 `process.env.NODE_ENV` / `import.meta.env`，使该分支不再命中 |

- 测试：vitest 启动即要求 esbuild 打包配置，沙箱内不可用，故改用 Node 内置测试运行器
  `node --test --test-isolation=none`（同进程避免 spawn），断言内容不变。
- `npm run dev` 的**依赖预打包**在 Vite 5.1+ 固定使用 esbuild，沙箱内无法启动；`build` 不受影响。
  dev 请在普通终端运行。
- 构建输出是 `web/dist`（本仓库 `libs/**` 对当前沙箱会话只读）。需要包内副本时用
  `scripts/build_web.ps1 -CopyToPackage` 在具备写权限的环境执行。

## 4. 产物与体积（实测）

`npm run build`（2026-10-18，terser、无 sourcemap、无 CSS 压缩）：

| 文件 | 原始 | gzip |
|---|---|---|
| `dist/assets/index-*.js`（全站单包：React/路由/Radix/markdown/文件页/设置页） | 886.63 kB | **264.19 kB** |
| `dist/assets/index-*.css` | 43.94 kB | 9.64 kB |
| `dist/index.html` | 1.29 kB | 0.67 kB |

首屏 JS（单个入口包）**264.2 kB gzip**，低于 350 kB 预算；`dist/index.html` 引用哈希资源
`/assets/index-<hash>.js|css`。

## 5. 部署与回滚

`app.py` 的 `WEB_DIST` 解析顺序：`KH_WEB_DIST` 环境变量 → 仓库 `web/dist`（存在 `index.html`）→
包内 `libs/ktem/ktem/web/dist`。因此：

- 运行时**不需要 Node**：`web/dist` 已提交，FastAPI 直接静态托管（`/assets/*` + SPA fallback）。
- 改了前端后重启服务即可生效（`WEB_DIST` 在启动时解析）。
- **一键回滚**：`KH_WEB_UI=0` 启动，Gradio 回到 `/`，React 界面不再挂载。
- 迁移期间旧界面始终可用：`/legacy`。

## 6. 后端接口

全部走 `credentials: "include"` 的 HttpOnly cookie：

- `auth/me|login|logout`，`meta`，`conversations` CRUD + `feedback`，`settings`
- 聊天流：`POST /api/v1/conversations/{id}/messages`（`fetch` + `ReadableStream` 手写 SSE 解析，
  支持半包/多事件/`\r\n`；不用 `EventSource`，因为它是 GET）
- 文件域（M2，10 条）：`GET /files?index_id&query`、`POST /files/upload`（multipart → SSE
  `progress|done|error`）、`DELETE /files/{id}`、`POST /files/{id}/reindex`（SSE）、
  `GET /files/{id}/chunks?type=`、`GET /files/{id}/download`、`GET/POST /groups`、
  `PATCH/DELETE /groups/{id}`
- 设置：`GET /settings`、`GET /settings/schema`（分组 + 字段类型/选项/默认值）、`PUT /settings`

SSE 事件：`start`（可带 `warning`）、`token`、`reset`、`evidence`、`mindmap`、`plot`、
`title`、`suggestions`、`done`、`error`。实现细节：

- `done` 可能带 `name`，随后还有 `title`，两者都用于更新会话标题；
- 管线失败发 `error` 后流结束（不落库），界面显示内联错误卡并允许重试（`regenerate: true`）；
- `evidence[].page` 可能为 `null`；`file_path` 可能是绝对 Windows 路径，打开原文用
  `/legacy/file=<encodeURIComponent(path)>#page=N`；
- 请求 `overrides`：`reasoning/language/citation` 取各自 `default`，`llm` 默认 `""`，
  `mindmap` 默认取 `meta.features.mindmap`（能力开关，不等于默认开启）并总是显式发送布尔值；
- 会话详情里的 `legacy_evidence` 字段忽略。

## 7. Mock

`src/lib/mock.ts` 只在 `VITE_USE_MOCK=1` 时通过动态 `import()` 加载，默认关闭，生产路径不加载：

```powershell
$env:VITE_USE_MOCK = "1"; npm run dev
```

## 8. 当前范围与已知限制

已实现：`/login`、`/chat`、`/chat/:id`（Rail + 可拖拽会话侧栏 + 聊天主区 + 证据抽屉/浮层）、
空状态与建议问题、流式回答（光标/markdown/代码高亮/停止/重试/复制/反馈）、引用点击联动证据、
聊天设置弹层、命令面板（⌘/Ctrl+K）、明暗主题与中英界面、1024/1280/820 响应式。

M2：`/files`（搜索、原生上传/URL、文件表与行操作、分块抽屉、分组 CRUD）与
`/settings`（schema 驱动表单、分组导航、吸底保存与未保存提示）已替换占位页。
`/resources`、`/help` 仍为“经典界面”卡片（M3）。

限制：

1. 沙箱内无浏览器：交互与视觉只做代码级/接口级验证；`npm run dev` 的 HMR 需在普通环境确认。
2. 入口为单个 JS 包（264.2 kB gzip）；后续页面迁移时再按路由拆分。
3. 首屏依赖 `/api/v1/meta` 与会话数据，接口慢时显示骨架屏。
4. 沙箱禁止向新建子目录写文件（`mkdtemp` 后写入即 `Permission denied`），因此**原生上传**
   在本会话只能验证到 403（环境限制）；上传/重建索引的接口逻辑由后端 17 个测试覆盖，
   真实上传需在普通环境点一次。
5. 设置页不处理用户密码（仍在 `/legacy` 的用户设置里）。
