# 极客配单 (Geek Config)

一个**前后端分离的数码选购 Agent 应用**：用户用自然语言描述需求（比如"5000 元入门剪辑电脑"），Agent 自主规划任务、调用工具（查商品/查库存/算价/下单），并带**降级 + 可观测 + 评测 + 记忆**四件套。同时提供**传统选购路径**：商品卡片加购 → 购物车抽屉 → 结算下单（库存校验 + 自动扣库存）。

> GitHub: https://github.com/jijizaza123/shop-agent （提交前替换为真实链接）
> 难点叙事 / 简历 bullet / 面试口述：见 `难点叙事.md`

## 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | React 18 + Vite + TypeScript + Ant Design + axios | 组件化 UI，工程完整 |
| 后端 | Python + FastAPI + Uvicorn | 异步 API，CORS 配好 |
| Agent | **LangGraph**(状态图 + 条件边 + 降级路由) | 可编排、可观测、不绑模型生态 |
| LLM | Agnes-3.0-flash（OpenAI 兼容协议） | 切换模型只改 `.env` 一行 |
| 数据库 | PostgreSQL + SQLAlchemy 2.0 | 真实工程化的 ORM + 关系型 |
| 工具 | 4 个 Function Calling 工具 | 查商品/查库存/算价/下单 |
| 购物车 | Order 表复用(status='cart') + 库存校验 + 扣库存 | 加购/改量/结算一条链路 |
| 记忆 | AgentMemory 表 + 会话级短期记忆 + 用户偏好长期记忆 | 多轮上下文 / 个性化推荐 |
| 可观测 | AgentTrace 表 + state.trace（节点级耗时/工具/降级） | 前端可展开查看 |
| 评测 | evals/runner.py（mock/real 双模式） | 隔离外部依赖, 回归可复现 |

## 核心功能

- **Agent 选购**：自然语言描述 → LangGraph 规划 → 调工具（查商品/查库存/算价/下单）→ 带降级回复
- **会话记忆**：多轮对话保留上下文（短期）+ 抽取用户偏好（预算/品类）写入长期记忆，下次推荐个性化
- **传统选购**：商品卡片「加入购物车」→ 购物车抽屉（改数量/移除）→ 结算下单（库存校验 + 自动扣库存 + 生成 pending 订单）
- **可观测**：每次 Agent 对话落库，前端可展开查看节点耗时/工具调用/降级标记
- **量化评测**：20 个 case，mock/real 双模式（mock 隔离外部依赖做回归，real 测真实语义），6 项指标

## 目录结构

```
shop/
├── backend/
│   ├── .env                # DATABASE_URL + AGNES_API_KEY(已在 .gitignore)
│   ├── .env.example        # 模板, copy 成 .env 再填真实 key
│   ├── requirements.txt
│   ├── start_backend.sh / .bat   # 一键启动(装依赖+建表+种子+起服务)
│   ├── test_smoke.py       # 自检: 路由 + Agent 对话
│   ├── evals/
│   │   ├── dataset.json    # 20 case
│   │   ├── runner.py       # 跑评测(--mock / --real)
│   │   ├── report.mock.json# mock 报告(可复现, 已 gitignore)
│   │   └── report.json     # real 报告(打 Agnes, 已 gitignore)
│   └── app/
│       ├── main.py         # FastAPI 入口
│       ├── llm_client.py   # LLM 调用收口(重试/超时/工具注册)
│       ├── db/
│       │   ├── database.py # SQLAlchemy 模型 Product/Order/AgentTrace/AgentMemory
│       │   └── seed.py     # 20 个数码 SKU(含 4 档显卡, 幂等增量)
│       ├── api/            # 路由: products(含购物车)/orders/agent/evals/traces
│       └── agent/
│           ├── tools.py    # 4 个工具定义
│           ├── prompts.py  # 系统提示词
│           ├── memory.py   # 记忆: 会话短期 + 用户偏好长期
│           ├── mock_llm.py # 确定性伪 LLM(mock 评测用)
│           └── graph.py    # LangGraph 状态图(核心, 含记忆注入)
└── frontend/
    ├── package.json
    └── src/
        ├── api/client.ts   # API 封装(商品/购物车/Agent)
        ├── components/
        │   ├── ProductList.tsx   # 商品卡片 + 加入购物车
        │   ├── CartDrawer.tsx    # 购物车抽屉 + 结算
        │   └── AgentPanel.tsx    # Agent 对话 + trace 展开
        └── App.tsx         # 布局: 商品 + Agent + 购物车 Badge
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
copy .env.example .env          # Windows: copy .env.example .env
# 编辑 .env 填 AGNES_API_KEY
start_backend.bat               # 一键: 装依赖 + 建表 + 种子 + 起服务(:8000)
# 或手动:
python -m app.db.seed
uvicorn app.main:app --reload --port 8000
# 验证: curl http://localhost:8000/health
```

### 3. 前端
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

打开浏览器 http://localhost:5173 ：
- 左侧商品列表（含 4 档显卡），点「**加入购物车**」→ 右上角购物车抽屉 → 改数量/结算
- 右侧 Agent 对话，试一句"帮我配 5000 元剪辑电脑"

## 购物车 & 结算流程

```
商品卡片 [加入购物车]
   └─ POST /api/cart/add {product_id, qty}      校验库存 -> 累加到购物车
购物车抽屉
   ├─ POST /api/cart/qty {product_id, qty}     改数量 / qty=0 移除
   └─ POST /api/cart/checkout                   校验库存 -> 扣库存 -> 生成 pending 订单 -> 清车
```

实现说明：购物车复用 `orders` 表（`status='cart'` 的一行存当前车），结算时校验库存、扣减 `products.stock`、把该行转为 `status='pending'` 的正式订单。

## 记忆模块

会话级记忆，两层：
- **短期（会话）**：`AgentMemory` 表按 `session_id` 存最近 N 轮对话，多轮问答保留上下文（"我刚才说的那个显卡还有更便宜的吗"能接得上）。
- **长期（用户偏好）**：从对话里抽取稳定偏好（预算区间、品类倾向、品牌偏好）落库，下次同用户请求时注入 system prompt，实现"记住你预算 5000、偏好 Intel"的个性化推荐。

> 面试点：短期=滑窗/摘要控上下文长度，长期=偏好抽取（这里用关键词启发式，生产可换成 LLM 判断"是否值得长期记"）。

## 跑评测

```bash
cd backend
python -m evals.runner --mock     # 默认: 确定性 MockLLM, 不碰 Agnes, 永远可复现(测工具/降级链路)
python -m evals.runner --real     # 打真实 Agnes, 测语义理解(会受限流影响)
# 指标: 任务成功率 / 工具调用准确率 / 关键词命中 / 总Token / 平均延迟 / 降级率
```

**为什么分两层**：真实 LLM 评测有两个致命问题——非确定性（同输入不同答案，没法回归）+ 外部依赖（限流/额度把成功率污染到 10%）。mock 层用确定性规则替代 LLM 的"选工具"决策，隔离外部依赖，专门回归"工具链路 + 降级"是否正确；real 层小样本测语义能力。两层分开看，避免被限流数字误导。

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/products?keyword=&category=&max_price=` | 商品查询 |
| GET | `/api/products/categories` | 类别列表 |
| GET | `/api/cart` | 当前购物车 |
| POST | `/api/cart/add` | 加购 |
| POST | `/api/cart/qty` | 改量/移除 |
| POST | `/api/cart/checkout` | 结算下单 |
| GET/POST | `/api/orders` | 订单查询/手动下单 |
| POST | `/api/agent/chat` | Agent 对话（带会话记忆 + 用户偏好注入） |
| GET | `/api/evals/report` | 评测报告(real) |
| GET | `/api/evals/report/mock` | 评测报告(mock, 可复现) |
| GET | `/api/traces` | Agent 可观测历史 |

## 架构图

```
┌────────────────────────────────────────────┐
│  前端 React (5173)                         │
│  ├─ ProductList ── GET /api/products       │
│  │   └─ [加入购物车] ── POST /api/cart/add │
│  ├─ CartDrawer ── GET /cart, POST /checkout│
│  └─ AgentPanel  ── POST /api/agent/chat   │
└─────────────────┬──────────────────────────┘
                  │ fetch(axios)
                  ▼
┌────────────────────────────────────────────┐
│  后端 FastAPI (8000)                       │
│  ├─ products.py  (含 /cart /cart/add /checkout) │
│  ├─ agent.py ── run_agent()                │
│  │   └─ LangGraph                          │
│  │      plan → router → {router|fallback} │
│  │                       → answer           │
│  │      router 调 LLM(Agnes) + 工具        │
│  │      工具: search_products/check_stock/ │
│  │            calculate_total/create_order  │
│  └─ evals.py  /traces.py  /orders.py       │
└─────────────────┬──────────────────────────┘
                  │ psycopg (SQLAlchemy)
                  ▼
┌────────────────────────────────────────────┐
│  PostgreSQL shop_db                        │
│  products / orders(含 status=cart 购物车) │
│  / agent_traces                            │
└────────────────────────────────────────────┘
```

## 可讲的点（面试）

1. **为什么选 LangGraph**：状态可管理、可观测、不绑模型生态、支持条件边 + 降级路由。
2. **降级策略三级**：工具失败自动重试（tenacity 指数退避）→ 连续 3 次失败进 fallback 节点（基于缓存给降级回复）→ 最终提示用户人工接管。
3. **可观测**：每次对话落 `AgentTrace` 表 + state.trace（节点级耗时/工具/降级标记），前端可展开查看。
4. **评测（mock/real 双模式）**：针对 LLM 评测"非确定 + 外部依赖污染"两大痛点，mock 层用确定性伪 LLM 隔离外部依赖专测工具/降级链路（永远可复现），real 层小样本测语义能力。简历上放 mock 数字（成功率 90%），不冒充被限流污染的 real 数字。
5. **记忆模块**：会话短期记忆（滑窗控上下文）+ 用户长期偏好（预算/品类/品牌，关键词启发式抽取，注入 system prompt 做个性化推荐）。
6. **购物车设计取舍**：用 `orders` 表 `status='cart'` 行复用当购物车，避免为"临时状态"单建一张表；结算走「校验库存 → 扣库存 → 转 pending 订单 → 清车」一条原子链路。
6. **踩坑**：
   - LangGraph 节点返回 `{}` 会清空 state → 必须 `Annotated[list, add]` 累加器
   - 工具实现注册在 `llm_client` 不在 `tools` 模块，graph.py 要正确 import
   - JSON 文件不能写 `#` 注释（dataset.json 头几行注释曾让评测整体没跑）
   - `__main__` 少写一个下划线成 `__main`，导致 `python -m` 入口从不执行
   - SQLAlchemy `s.close()` 后读 `cart.total` 报 `DetachedInstanceError` → 必须在 close 前存局部变量
   - 中文路径下 Postgres 连接要用 `127.0.0.1` 避开 `::1`
   - Agnes 免费额度限流 429 → 评测要控制并发 + 加冷却（限流下会触发降级路径，正好验证 fallback 逻辑）
   - 记忆表 `AgentMemory` 要带 `session_id` 索引，否则多会话查询会全表扫

