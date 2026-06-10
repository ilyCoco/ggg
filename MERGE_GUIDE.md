# 智能助手功能分支 — 合并指南

## 分支信息
- 仓库：https://github.com/ilyCoco/ggg
- 分支：`main`（即 `claude/mystifying-kepler-a552a4`）
- 基于原版第一个 commit 之后的所有改动

## 改动总览

### 新增文件（3个）
| 文件 | 功能 | 是否可能冲突 |
|---|---|---|
| `agent_core/llm_streaming.py` | SSE 流式 LLM 客户端 | 无冲突 |
| `agent_core/tools/announcement_tools.py` | Agent 公告发布/列表工具 | 无冲突 |
| `pages/10_🖥️_指挥中心.py` | Agent 指挥中心大屏 | 无冲突 |

### 修改文件（按冲突风险排列）

**高风险（黑板的改动可能也碰了这些文件）：**

| 文件 | 我的改动 |
|---|---|
| `agent_core/memory.py` | 新增 `agent_activity_log` 表（含 user_id）、`log_agent_activity()`、`get_agent_activity_log()`、`get_agent_stats()` 函数 |
| `agent_core/coordinator.py` | 新增 announcement_tools 注册、路由 prompt 加了 announcement 领域 |
| `database/connection.py` | 新增 `kb_attachments` 表定义 |
| `app.py` | 仪表盘简报缓存（避免每次刷新重跑 AI）、实时通知/审批数量查询 |

**中风险：**

| 文件 | 我的改动 |
|---|---|
| `agent_core/domain_agents.py` | 通用助理 prompt 加了公告能力说明 |
| `agent_core/llm_client.py` | 新增 `stream_chat()` 方法 |
| `agent_core/tools/kb_tools.py` | 新增 `list_kb_entries`、`get_entry_detail`，搜索返回附件信息 |
| `agent_core/tools/task_tools.py` | 新增 `delete_task` 工具 |
| `agent_core/tools/calendar_tools.py` | 新增 `delete_event` 工具 |
| `agent_core/tools/general_tools.py` | 新增 `delete_approval` 工具 |
| `components/thinking_panel.py` | 全新 UI：时间线样式、耗时/Token 标签、暗色状态栏 |
| `components/__init__.py` | 导出更新 |
| `knowledge_base/manager.py` | 新增附件 CRUD 函数、搜索 fallback 到 LIKE |
| `knowledge_base/__init__.py` | 导出更新 |
| `approvals/manager.py` | 新增 `delete_approval` 函数 |
| `approvals/__init__.py` | 导出更新 |
| `announcements/manager.py` | 创建公告时自动通知所有用户 |

**低风险（纯 UI）：**

| 文件 | 我的改动 |
|---|---|
| `pages/0_🤖_智能助手.py` | 打字机流式输出 + 实时推理面板 + 按用户ID隔离聊天 |
| `pages/2_📚_知识库.py` | 新建条目表单、附件上传/预览、文件图标 |
| `pages/5_📋_审批管理.py` | 删除按钮、历史按角色过滤 |
| `pages/6_📅_日程管理.py` | 日历可点击、编辑删除日程 |
| `.gitignore` | 加了 `data/*.db` 和 `uploads/` |

## 合并建议

如果他在另一个 worktree 或分支上开发，最简单的合并方式：

```bash
# 1. 拉取我的分支
git fetch origin main

# 2. 切到他的分支，合并我的改动
git merge origin/main

# 3. 解决冲突（重点关注这些文件）
#    - agent_core/memory.py（黑板 vs 活动日志表可能有冲突）
#    - agent_core/coordinator.py（工具注册顺序可能有冲突）
#    - database/connection.py（表定义顺序可能有冲突）
#    - app.py（仪表盘逻辑可能有冲突）
```

如果冲突太多不好合并，让他告诉他的 Claude：
> "我的同事在 memory.py 里加了 agent_activity_log 表和活动日志函数，在 coordinator.py 里注册了 announcement_tools，在 kb_tools.py 里加了 list_kb_entries 工具。请你参考 origin/main 分支的这些改动，在我的代码上实现同样的功能，不要覆盖我的黑板改动。"

这样他的 Claude 会参考你的代码，在他自己的代码基础上重新实现，不会破坏黑板功能。

## 运行验证

```bash
cd D:\code\geshi-Claude\.claude\worktrees\mystifying-kepler-a552a4
# 配 API Key（智能助手需要）
echo DEEPSEEK_API_KEY=你的key > .env
echo DEEPSEEK_BASE_URL=https://api.deepseek.com >> .env
echo DEEPSEEK_MODEL=deepseek-chat >> .env
streamlit run app.py --server.port 8503
```

登录 admin / admin123，检查：
1. 智能助手 → 发消息有打字机效果、右侧推理面板
2. 知识库 → 能上传 PDF 附件并预览
3. 日程管理 → 点击日历格子能看日程
4. 指挥中心 → 深色仪表盘正常显示
5. 审批管理 → 能删除已完成的审批
