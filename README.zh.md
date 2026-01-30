# Search Agent Framework

## 架构概览

这是一个两层分层系统，将复杂查询分解为并行子任务，由专用智能体执行：

- **第一层 (Orchestrator)**: 使用 LangChain 的顶层编排器，通过 MCP 调用 `search_worker_pool`
- **第二层 (SearchAgent)**: 执行具体的搜索任务

## 核心特性

- 🚀 **大规模并行化**: 最多 50 个并发搜索执行器
- 🏗️ **两层架构**: Orchestrator → SearchWorkers
- 🔧 **MCP 集成**: 通过 Model Context Protocol 实现进程隔离
- 🎯 **专用执行器**: Search
- 🛡️ **容错性**: 优雅降级和重试逻辑

## 快速开始

```python
from search_agent.runtime import create_orchestrator
from search_agent.configuration import SearchAgentConfig
from search_agent.shared import RunPaths
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

## 项目结构

```
SearchAgent/
├── README.md                    # 项目说明
├── ARCHITECTURE.md              # 详细架构文档
├── requirements.txt             # Python依赖
├── pool_config.yaml            # 工作池配置
└── src/
    └── search_agent/
        ├── orchestration/       # 编排层
        │   └── orchestrator.py  # Orchestrator（连接 search_worker_pool）
        ├── coordination/        # 工具类
        │   └── _worker_wrapper.py  # Worker包装器
        ├── execution/           # 执行层
        │   └── search_executor.py
        ├── infrastructure/      # 基础设施层
        │   └── firecrawl-mcp-server/  # Firecrawl MCP Server
        ├── configuration/       # 配置系统
        ├── runtime/            # 运行时服务
        └── shared/             # 共享代码
```

详细的项目结构请参考 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 技术栈

- **编排层**: LangChain (Orchestrator)
- **执行层**: LangChain (SearchAgent)
- **通信**: Model Context Protocol (MCP)
- **并行化**: asyncio.gather（search_worker_pool 内部调度）
- **外部服务**: Firecrawl (搜索)

## 安装

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 构建 Firecrawl MCP 服务器

Firecrawl MCP 服务器位于 `src/search_agent/infrastructure/firecrawl-mcp-server/`。

**手动安装**

```bash
cd src/search_agent/infrastructure/firecrawl-mcp-server
rm -rf node_modules package-lock.json
npm install
npm run build
```

**故障排除**: 如果遇到 `Cannot find module '../lib/tsc.js'` 错误，请删除 `node_modules` 和 `package-lock.json` 后重新安装。

## 配置

### 工作池配置

编辑 `pool_config.yaml` 来调整工作池大小：

```yaml
pools:
  search:
    max_pool_size: 50
```

### 环境变量

设置必要的 API 密钥：

```bash
export OPENAI_API_KEY="your-api-key"
export FIRECRAWL_API_KEY="your-firecrawl-key"
```

### Firecrawl API Key

如果没有 API Key，可以从 https://www.firecrawl.dev/app/api-keys 获取。

## 使用示例

更多使用示例请参考 `examples/` 目录下的 Jupyter Notebook：

- `examples/agents/search_agent_test.ipynb` - SearchAgent 使用示例
- `examples/managers/search_manager_test.ipynb` - Orchestrator 端到端测试

## 架构说明

详细架构说明请参考 [ARCHITECTURE.md](ARCHITECTURE.md)，包括：

- 完整的目录结构
- 核心组件说明
- 数据流程图
- 命名规范
- 使用示例

