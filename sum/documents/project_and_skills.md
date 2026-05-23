# agent_platform 项目与 Skills 长期文档

> 维护约定：本文档长期存在，后续每次做较大功能、架构、部署、依赖或协作流程调整时，都应同步更新。建议把新增内容写入对应章节，并在“更新记录”里留下日期和摘要。

## 1. 项目定位

`agent_platform` 当前是一个智能旅游规划 Agent 平台，包含：

- 后端：FastAPI + LangChain / LangGraph / deepagents，负责用户认证、会话管理、流式聊天、子 Agent 调度、工具调用、RAG/向量检索相关能力。
- 前端：Vue 3 + Vite + TypeScript + Element Plus，负责登录注册、聊天会话列表、SSE 流式输出、Markdown 渲染和高德地图展示。
- 数据：PostgreSQL 保存用户和会话元数据，LangGraph checkpointer 保存对话上下文，`chroma_db`/RAG 数据用于知识检索。

当前代码目录里存在不少学习/实验文件，后续需要逐步区分“生产代码”和“实验代码”，避免团队开发时误改或误引用。

## 2. 当前目录地图

```text
piact_agent/
  backed/                 # 后端主代码，FastAPI 路由、Agent、CRUD、模型、工具
  travel_frontend/        # Vue/Vite 前端
  test/                   # 学习、验证、RAG 实验代码
  chroma_db/              # 本地向量库运行数据，已加入 .gitignore，不应入库
  my_skill/               # 团队共享的 Codex/Agent skills 与工作流资料
  sum/documents/          # 项目长期文档、总结、协作说明
```

## 3. 后端概览

主要入口：

- `backed/main.py`：FastAPI 应用入口，注册用户和聊天路由，配置 CORS，启动/关闭 checkpointer。
- `backed/routers/users.py`：注册、登录、用户信息、资料更新、密码修改。
- `backed/routers/chat.py`：会话列表、新建/删除会话、历史消息、`/api/chat/stream` SSE 流式聊天。
- `backed/agent/sup_agent.py`：主 Agent，按意图委派给天气、搜索、路线规划等子 Agent。
- `backed/agent/sub_agent/`：子 Agent 定义。
- `backed/agent/agent_tools/`：天气、搜索、图片、MCP/地图等工具。
- `backed/crud/`、`backed/models/`、`backed/schema/`：数据库、ORM、Pydantic 请求/响应结构。

当前需要优先注意：

- `backed/crud/db_config.py` 中存在硬编码 PostgreSQL 连接串，后续应迁移到 `.env` 或配置系统。
- 多处中文注释/字符串呈乱码，说明编码历史不一致，后续应统一为 UTF-8。
- CORS 当前允许全部来源，生产环境需要收紧。
- `.env`、日志、向量库、缓存已通过根目录 `.gitignore` 排除，避免首次上传泄露。

## 4. 前端概览

主要入口：

- `travel_frontend/package.json`：前端依赖和脚本。
- `travel_frontend/src/main.ts`：Vue 应用初始化。
- `travel_frontend/src/router/index.ts`：路由和登录态守卫。
- `travel_frontend/src/utils/request.ts`：Axios 实例、Token 注入、错误处理。
- `travel_frontend/src/views/auth/`：登录、注册页面。
- `travel_frontend/src/views/chat/index.vue`：聊天主界面、会话列表、SSE 消息接收、工具状态展示。
- `travel_frontend/src/components/AMapCard.vue`：地图数据展示。

常用命令：

```powershell
cd D:\langchain_dev\piact_agent\travel_frontend
npm install
npm run dev
npm run build
```

当前需要优先注意：

- 前端也存在中文乱码，需要统一编码并修复显示文案。
- `request.ts` 的 `baseURL` 为空，开发环境依赖 Vite 代理或同源部署，后续应显式配置环境变量。
- 聊天页逻辑较集中，后续可拆分为 composable、消息组件、会话侧栏组件。
- Markdown 当前允许 `html: true`，需评估 XSS 风险。

## 5. 本地开发启动参考

后端参考：

```powershell
cd D:\langchain_dev\piact_agent
uvicorn backed.main:app --host 0.0.0.0 --port 8000 --reload
```

前端参考：

```powershell
cd D:\langchain_dev\piact_agent\travel_frontend
npm run dev
```

实际启动前需要确认：

- PostgreSQL 数据库 `travel_agent` 可连接。
- `.env` 中配置了模型、Embedding、搜索、地图、图片等 API Key。
- 前端 API 代理或后端地址已配置。

## 6. GitHub 上传与仓库约定

目标远程仓库：

```text
https://github.com/SSA-AFK/agent_platform.git
```

首次上传建议流程：

```powershell
git init
git branch -M main
git remote add origin https://github.com/SSA-AFK/agent_platform.git
git add .
git status --short
git commit -m "Initial project import"
git push -u origin main
```

上传前必须检查：

- 不提交 `.env`、数据库文件、向量库、日志、`node_modules`、IDE 私有配置。
- 若发现密钥已经进入 Git 历史，应立刻更换密钥并清理历史。
- 对团队成员公开前，先审查硬编码账号、密码、Token、API Key。

## 7. my_skill 目录约定

`my_skill/` 用于存放团队共享的 Agent/Codex 工作流资料，不等同于 Codex 全局安装目录。团队成员可以在这里查看、版本化、讨论 skill 的用途和适用边界。

建议结构：

```text
my_skill/
  superpowers/            # 计划放置 obra/superpowers 工作流资料
  project-workflows/      # 本项目专属工作流 skill
```

当前计划引入：

- `superpowers`：一组强调小步迭代、测试驱动、计划检查、代码审查的 Agent 工作流。已放在 `my_skill/superpowers/`，并通过 Git submodule 管理。
- `project-workflows`：本项目专属工作流 skill，位于 `my_skill/project-workflows/SKILL.md`，用于指导团队修改后端、前端、Agent 工具和长期文档。

注意：如果要让 Codex 自动识别某个 skill，通常需要安装到 Codex 的全局 skills 目录；放在 `my_skill/` 中主要用于团队共享和项目内版本管理。

团队拉取包含 submodule 的项目时，建议使用：

```powershell
git clone --recurse-submodules https://github.com/SSA-AFK/agent_platform.git
```

如果已经克隆过项目，可在项目根目录执行：

```powershell
git submodule update --init --recursive
```

## 8. 后续优化路线

高优先级：

- 安全：移除硬编码数据库连接串；补 `.env.example`；统一环境变量读取；检查 API Key 泄露。
- 编码：批量修复中文乱码并统一 UTF-8；避免修复过程中改变业务语义。
- 后端配置：将 CORS、数据库、模型、工具 Key、日志等级改为配置驱动。
- 前端安全：关闭或限制 Markdown HTML 渲染，处理 XSS 风险。
- 入库边界：把实验代码、测试数据、生产代码的目录边界整理清楚。

中优先级：

- 后端错误处理与响应模型统一；增加请求校验和更明确的异常码。
- SSE 协议抽象：统一 message_chunk、tool_call、map_data、error、done 等事件格式。
- 前端聊天页拆分：会话侧栏、消息列表、输入区、工具状态、地图卡片独立组件化。
- 增加基础测试：用户认证、会话 CRUD、聊天历史、前端构建检查。

长期方向：

- 引入迁移工具，例如 Alembic。
- 增加 Docker Compose，统一 PostgreSQL、后端、前端启动。
- 为 Agent 工具调用增加可观测性，包括 trace id、工具耗时、错误分类。
- 建立项目专属 skill，让团队后续优化更稳定、可重复。

## 9. 更新记录

- 2026-05-23：创建文档初版；梳理项目结构、上传 GitHub 注意事项、skill 目录约定和后续优化路线。
- 2026-05-23：新增 `my_skill/project-workflows/SKILL.md`；记录 `superpowers` 本地下载状态和后续入库选择。
- 2026-05-23：将 `my_skill/superpowers` 明确为 Git submodule，并补充团队拉取方式。
