# Search Agent Framework - 测试示例

本目录包含 Search Agent Framework 的测试和示例代码。

## 目录结构

```
examples/
├── agents/                    # Executor 层测试
│   └── search_agent_test.ipynb      # SearchExecutor 测试
└── managers/                  # Orchestrator 层测试
    └── search_manager_test.ipynb    # Orchestrator 测试
```

## 使用说明

### 前置要求

1. **环境变量设置**
   ```bash
   export OPENAI_API_KEY="your-api-key"
   export FIRECRAWL_API_KEY="your-firecrawl-key"
   ```

2. **依赖安装**
   ```bash
   pip install -r ../requirements.txt
   ```

3. **Firecrawl MCP 服务器构建**
   ```bash
   cd ../src/search_agent/infrastructure/firecrawl-mcp-server
   npm install
   npm run build
   ```

### 运行测试

1. **SearchExecutor 测试** (`agents/search_agent_test.ipynb`)
   - 测试单个 SearchExecutor 的基本功能
   - 验证 Firecrawl MCP 服务器连接
   - 测试基础搜索和网页爬取功能

2. **Orchestrator 测试** (`managers/search_manager_test.ipynb`)
   - 测试 Orchestrator 的完整功能
   - 验证 `execute_subtasks` 工具的并行执行
   - 测试多个 SearchExecutor 的并行工作
   - 覆盖了完整的端到端流程（任务分解 → 并行执行 → 结果合成）

## 注意事项

- 所有测试文件已更新为使用新的 `search_agent` 模块路径和命名规范
- 确保在运行测试前正确设置环境变量
- Orchestrator 测试可能需要较长时间（需要初始化多个 SearchExecutor workers）
