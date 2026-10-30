# 极客配单 (Geek Config)

一个**前后端分离的数码选购 Agent 应用**：用户用自然语言描述需求（比如"5000 元入门剪辑电脑"），Agent 自主规划任务、调用工具（查商品/查库存/算价/下单），并带**降级 + 可观测 + 评测**三件套。

## 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | React 18 + Vite + TypeScript + Ant Design + axios | 组件化 UI，工程完整 |
| 后端 | Python + FastAPI + Uvicorn | 异步 API，CORS 配好 |
| Agent | **LangGraph**(状态图 + 条件边 + 降级路由) | 可编排、可观测、不绑模型生态 |
| LLM | Agnes-3.0-flash（OpenAI 兼容协议） | 切换模型只改 `.env` 一行 |
| 数据库 | PostgreSQL + SQLAlchemy 2.0 | 真实工程化的 ORM + 关系型 |
| 工具 | 4 个 Function Calling 工具 | 查商品/查库存/算价/下单 |
| 可观测 | AgentTrace 表 + state.trace（节点级耗时/工具/降级） | 前端可展开查看 |
| 评测 | evals/runner.py（成功率/工具准确率/Token/延迟/降级率） | 量化 Agent 质量 |

## 目录结构

```
shop/
├── backend/
│   ├── .env                # DATABASE_URL + AGNES_API_KEY(已在 .gitignore)
│   ├── requirements.txt
│   ├── test_smoke.py       # 自检: 路由 + Agent 对话
│   ├── evals/
│   │   ├── dataset.json    # 20 case
│   │   ├── runner.py       # 跑评测
│   │   └── report.json     # 评测报告(生成物)
│   └── app/
│       ├── main.py         # FastAPI 入口
│       ├── llm_client.py   # LLM 调用收口(重试/超时/工具注册)
│       ├── db/
│       │   ├── database.py # SQLAlchemy 模型 Product/Order/AgentTrace
│       │   └── seed.py     # 16 个数码 SKU
│       ├── api/            # 5 个路由: products/orders/agent/evals/traces
│       └── agent/
│           ├── tools.py    # 4 个工具定义
│           ├── prompts.py  # 系统提示词
│           └── graph.py    # LangGraph 状态图(核心)
└── frontend/
    ├── package.json
    └── src/
        ├── api/client.ts   # API 封装
        ├── components/
        │   ├── ProductList.tsx
        │   └── AgentPanel.tsx
        └── App.tsx
```

## 快速开始

### 1. 数据库
```bash
# 确保 Postgres 在 127.0.0.1:5432 运行, 库 shop_db 已建
# 用户: postgres / 密码: 050408 (按需改 backend/.env)
```

### 2. 后端
```bash
cd backend
pip install -r requirements.txt
# 复制 .env.example -> .env, 填 AGNES_API_KEY
python -m app.db.seed                # 建表 + 种子
uvicorn app.main:app --reload --port 8000
# 验证: curl http://localhost:8000/health
```

### 3. 前端
```bash
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

打开浏览器 http://localhost:5173 ，左侧商品列表 + 右侧 Agent 对话，试一句"帮我配 5000 元剪辑电脑"。

## 跑评测
```bash
cd backend
python -m evals.runner               # 跑 20 case, 生成 evals/report.json
```

## 架构图

```
┌────────────────────────────────────────────┐
│  前端 React (5173)                         │
│  ├─ ProductList ── GET /api/products       │
│  └─ AgentPanel  ── POST /api/agent/chat   │
└─────────────────┬──────────────────────────┘
                  │ fetch(axios)
                  ▼
┌────────────────────────────────────────────┐
│  后端 FastAPI (8000)                       │
│  ├─ products.py  /orders.py               │
│  ├─ agent.py ── run_agent()                │
│  │   └─ LangGraph                          │
│  │      plan → router → {router|fallback} │
│  │                       → answer           │
│  │      router 调 LLM(Agnes) + 工具        │
│  │      工具: search_products/check_stock/ │
│  │            calculate_total/create_order  │
│  └─ evals.py  /traces.py                  │
└─────────────────┬──────────────────────────┘
                  │ psycopg (SQLAlchemy)
                  ▼
┌────────────────────────────────────────────┐
│  PostgreSQL shop_db                        │
│  products / orders / agent_traces          │
└────────────────────────────────────────────┘
```

## 可讲的点（面试）

1. **为什么选 LangGraph**：状态可管理、可观测、不绑模型生态、支持条件边 + 降级路由。
2. **降级策略三级**：工具失败自动重试（tenacity 指数退避）→ 连续 3 次失败进 fallback 节点（基于缓存给降级回复）→ 最终提示用户人工接管。
3. **可观测**：每次对话落 `AgentTrace` 表 + state.trace（节点级耗时/工具/降级标记），前端可展开查看。
4. **评测**：20 case 量化 6 项指标（成功率/工具准确率/关键词命中/Token/延迟/降级率）。
5. **踩坑**：
   - LangGraph 节点返回 `{}` 会清空 state → 必须 `Annotated[list, add]` 累加器
   - 工具实现注册在 `llm_client` 不在 `tools` 模块，graph.py 要正确 import
   - JSON 文件不能写 `#` 注释
   - 中文路径下 Postgres 连接要用 `127.0.0.1` 避开 `::1`
