# Search Agent Framework - 系统架构文档

**Agent-to-Agent 分层多智能体系统，用于并行任务执行**

## 架构概览

这是一个 SearchManager + SearchWorker 的两层体系，将复杂查询分解为并行子任务，由 SearchWorker 池执行：

- **第一层 (Orchestrator / SearchManager)**: 使用 LangChain 的顶层编排器，负责任务分解与搜索策略，通过 MCP 调用 `search_worker_pool`
- **第二层 (SearchAgent / SearchExecutor)**: 具体执行搜索任务，通过 Firecrawl MCP 进行网页搜索和爬取

## 核心特性

- 🚀 **大规模并行化**: 最多 50 个并发 SearchAgent
- 🏗️ **两层架构**: Orchestrator → SearchWorkerPool → SearchAgent
- 🔧 **MCP 集成**: 通过 Model Context Protocol 实现进程隔离
- 🎯 **专用执行器**: Search
- 🛡️ **容错性**: 优雅降级和重试逻辑

## 目录结构

```
search_agent_framework/
├── README.md                    # 项目说明
├── ARCHITECTURE.md              # 架构文档（本文件）
├── requirements.txt             # Python依赖
├── pool_config.yaml            # 工作池配置
└── src/
    └── search_agent/
        ├── __init__.py
        │
        ├── orchestration/       # 编排层（顶层）
        │   ├── __init__.py
        │   └── orchestrator.py  # Orchestrator（SearchManager，连接 search_worker_pool）
        │
        ├── coordination/        # 协调层（工具类）
        │   ├── __init__.py
        │   └── _worker_wrapper.py      # Worker包装器
        │
        ├── execution/           # 执行层（底层）
        │   ├── __init__.py
        │   └── search_executor.py       # SearchExecutor（搜索执行器）
        │
        ├── agents/              # Worker层
        │   ├── __init__.py
        │   └── search_agent.py          # SearchAgent（搜索执行器）
        │
        ├── managers/            # Manager层
        │   ├── __init__.py
        │   └── search_manager_agent.py  # SearchManagerAgent
        │
        ├── mcp_servers/         # MCP服务器
        │   ├── __init__.py
        │   └── search_worker_pool.py    # SearchWorkerPool MCP Server
        │
        ├── infrastructure/      # 基础设施层
        │   ├── __init__.py
        │   └── firecrawl-mcp-server/    # Firecrawl MCP Server (Node.js)
        │
        ├── configuration/       # 配置系统
        │   ├── __init__.py
        │   ├── settings.py      # 主配置类
        │   ├── models.py        # 模型配置
        │   └── pools.py         # 工作池配置
        │
        ├── runtime/             # 运行时服务
        │   ├── __init__.py
        │   └── factory.py       # Factory（工厂函数，创建 Orchestrator）
        │
        ├── tools/               # 工具模块
        │   ├── __init__.py
        │   ├── tool_metadata.py  # 工具元数据
        │   └── url_status_manager.py  # URL 状态管理
        │
        └── shared/              # 共享代码
            ├── __init__.py
            ├── types.py         # 类型定义（RunPaths, Plan, PlanStep等）
            ├── utils.py         # 工具函数（json转markdown等）
            ├── version.py       # 版本信息
            └── _docker.py       # Docker配置和工具函数
```

## 核心组件说明

### 1. Orchestrator (`orchestration/orchestrator.py`)
- **职责**: 顶层编排器（SearchManager），负责任务分解、搜索策略，通过 MCP 调用 `search_worker_pool`
- **技术**: LangChain + MCP
- **功能**:
  - 将用户查询分解为多个 hops（子任务序列）
  - 应用搜索策略（ANCHOR & EXPAND, KEYWORD STRATEGY等）
  - 通过 MCP 调用 `execute_subtasks` 并行执行
  - 合成最终结果

### 2. SearchWorkerPool (`mcp_servers/search_worker_pool.py`)
- **职责**: MCP 服务器，管理 SearchAgent 池并提供 `execute_subtasks`

### 3. SearchAgent / SearchExecutor (`agents/search_agent.py`, `execution/search_executor.py`)
- **职责**: 执行具体的搜索任务
- **技术**: LangChain + Firecrawl MCP
- **功能**:
  - 使用 Firecrawl MCP 进行网页搜索和爬取
  - 提取和总结网页内容
  - 返回搜索结果

### 3. Firecrawl MCP Server (`infrastructure/firecrawl-mcp-server/`)
- Firecrawl MCP服务器（Node.js项目）
- 提供网页搜索、爬取、内容提取等功能
- 需要Node.js >= 18.0.0环境
- 首次使用前需要构建：`npm install && npm run build`

## 数据流

```
用户查询
  ↓
Orchestrator (分析、分解为hops，应用搜索策略)
  ├─ 通过 MCP 调用 search_worker_pool.execute_subtasks
  ↓
SearchWorkerPool (并行调度)
  ↓
SearchAgent 实例（每个实例独立执行一个子任务）
  ├─ 连接 Firecrawl MCP
  ├─ 执行搜索和爬取
  └─ 返回结果
  ↓
Orchestrator (聚合结果，合成最终答案)
```

## 架构特点

### 两层架构
- **第一层 (Orchestrator / SearchManager)**:
  - 负责任务分解和搜索策略
  - 通过 MCP 调用 `search_worker_pool`
  - 提供 `execute_subtasks` 工具给 LLM 调用

- **第二层 (SearchWorkerPool → SearchAgent)**:
  - WorkerPool 负责并行调度
  - SearchAgent 执行具体搜索任务

## 使用示例

### 基本使用

```python
from search_agent.runtime.factory import create_orchestrator
from search_agent.configuration.settings import SearchAgentConfig
from search_agent.shared.types import RunPaths
from pathlib import Path

# 创建配置
config = SearchAgentConfig()

# 创建运行路径
paths = RunPaths(
    internal_root_dir=Path("./cache"),
    external_root_dir=Path("./cache"),
    run_suffix="test",
    internal_run_dir=Path("./cache/test"),
    external_run_dir=Path("./cache/test"),
)

# 创建 Orchestrator（会连接 search_worker_pool）
orchestrator = await create_orchestrator(config=config, paths=paths)

# 执行查询
result = await orchestrator.run("研究前5个AI框架并创建对比表")

# 或流式获取实时更新
async for chunk in orchestrator.stream("复杂的多步骤查询..."):
    print(chunk)

# 清理资源
await orchestrator.close()
```

### 直接使用 Orchestrator

```python
from langchain_openai import ChatOpenAI
from search_agent.orchestration.orchestrator import Orchestrator

# 创建模型
chat_model = ChatOpenAI(model="gpt-5.1")

# 创建 Orchestrator
orchestrator = Orchestrator(name="orchestrator", model=chat_model)

# 初始化（会连接 search_worker_pool）
await orchestrator.start()

# 执行查询
result = await orchestrator.run("查找所有 Michelin 三星餐厅")

# 清理
await orchestrator.close()
```

## 配置

### 工作池配置

编辑 `pool_config.yaml` 来调整工作池大小：

```yaml
pools:
  search:
    max_pool_size: 50
  # 注意：browser, code, filesystem, media 配置已保留但不再使用
  # （当前架构只使用 search 池）
```

### 环境变量

设置必要的 API 密钥：

```bash
export OPENAI_API_KEY="your-api-key"
export FIRECRAWL_API_KEY="your-firecrawl-key"
```

## 命名规范

- **Orchestrator / SearchManagerAgent**: 顶层编排器，负责任务分解和协调
- **SearchWorkerPool**: MCP 服务器，管理 SearchAgent 池并执行并行子任务
- **SearchAgent / SearchExecutor**: 搜索执行器，执行具体的搜索任务

## 与旧版本的关系

### 旧版本架构（搜索分支）
```
HostAgent → ManagerHub → SearchManagerAgent → search_worker_pool → SearchAgent
```

### 新版本架构（对齐搜索分支）
```
Orchestrator(SearchManager) → search_worker_pool → SearchAgent
```

### 主要变化
1. **保留搜索分支逻辑**: SearchManager + SearchWorkerPool + SearchAgent 路线一致
2. **统一命名**: HostAgent → Orchestrator（语义等同 SearchManager）

## 故障排除

### SearchAgent 初始化失败
- 检查 Firecrawl MCP 服务器是否正确构建
- 确认 `FIRECRAWL_API_KEY` 环境变量已设置
- 检查 Node.js 版本 >= 18.0.0

### 并行执行失败
- 检查 `pool_config.yaml` 中的 `max_pool_size` 配置
- 确认有足够的系统资源支持多个 SearchAgent 实例

## 许可证

[根据项目实际情况填写]

## 贡献

[根据项目实际情况填写]
