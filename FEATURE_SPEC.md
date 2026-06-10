# 智能助手 + 办公系统增强 — 完整功能规格书

> 给同门的开发文档。按模块拆解，每个模块写清楚数据库变更、后端函数、Agent 工具、前端改动。可以逐个实现，互不依赖。

---

## 一、流式 LLM 输出 + 升级推理面板

### 1.1 新文件：`agent_core/llm_streaming.py`

流式 LLM 客户端，解析 SSE 协议，逐 token yield。

```python
# 核心类
class StreamingDelta:
    """type: "text" | "tool_call_start" | "tool_call_delta" | "tool_call_end" | "done" | "error" """

def stream_chat(config: LLMConfig, messages, tools=None, temperature=None):
    """Generator，逐次 yield StreamingDelta"""
    # 1. HTTP POST，body 加 "stream": True
    # 2. 用 urllib.request.urlopen 读取响应
    # 3. 逐行解析 "data: {json}" SSE 格式
    # 4. 遇到 "[DONE]" 则 yield StreamingDelta(type="done") 并返回
    # 5. tool_call 需要累积 arguments：id 出现时 yield tool_call_start，
    #    arguments 增量 yield tool_call_delta，完成时 yield tool_call_end
```

### 1.2 修改文件：`agent_core/llm_client.py`

在 `AgentLLMClient` 类新增方法：

```python
def stream_chat(self, messages, tools=None, temperature=None):
    """调用 _stream_chat(config, messages, tools, temperature)"""
    yield from _stream_chat(self.config, messages, tools, temperature)
```

导入：
```python
from .llm_streaming import StreamingDelta, stream_chat as _stream_chat
```

### 1.3 修改文件：`components/thinking_panel.py`

完全重写。保留三个导出函数：

```python
def render_thinking_panel(steps, timings=None, token_counts=None, expanded=False):
    """可折叠的时间线推理面板。每条步骤：
    - 左边 2px 竖线（颜色随步骤类型变）
    - 背景色随类型变（thought=紫底/tool_call=蓝底/observation=绿底/error=红底）
    - 右上角浮层：⏱ 耗时徽章 + 💰 Token 徽章
    - 底部汇总：共 N 步推理 · n 次思考 · n 次工具调用
    """

def render_agent_status(agents_active, tool_count, total_tokens=0, elapsed=0):
    """暗色顶部状态栏（background: #0F172A 渐变）。
    左侧 ⚡ AGENT STATUS，右侧工具调用数/Token/耗时。
    下方每个活跃 Agent 名 + 彩色圆点。Agent 名必须有 color 样式，不能默认灰色不可见。"""

STEP_ICONS = {"thought":"💭","tool_call":"🔧","observation":"📋","final_answer":"✅","error":"❌"}
```

### 1.4 修改文件：`pages/0_🤖_智能助手.py`

**流式打字机效果：** Agent 返回 answer 后，逐词打印（不是一次性显示）：

```python
# 打字机效果
words = answer.replace("\n", " \n ").split(" ")
for word in words:
    streamed += word + " "
    placeholder.markdown(streamed + "▌")
    time.sleep(max(0.008, min(0.025, 0.5 / max(len(word), 1))))
```

**推理步骤计时：** 用 `on_step` 回调中 `time.time()` 记录每个步骤耗时，存在 `step_timings` 列表传给 `render_thinking_panel`。

**聊天记录按用户隔离：**
```python
chat_key = f"chat_history_{user['id']}"
# 所有 st.session_state["chat_history"] 改为 st.session_state[chat_key]
```

**登出保护：** `app.py` 中登出按钮只清 `user` 和 `_briefing`，不调 `st.session_state.clear()`。

---

## 二、知识库附件系统

### 2.1 数据库变更：`database/connection.py`

在 `entry_tags` 表之后、`kb_entries_fts` 之前加：

```sql
CREATE TABLE IF NOT EXISTS kb_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    mime_type TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entry_id) REFERENCES kb_entries(id) ON DELETE CASCADE
);
```

### 2.2 修改文件：`knowledge_base/manager.py`

文件存储目录：`uploads/kb/{entry_id}/`

新增函数：
```python
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "kb")

def add_attachment(entry_id, uploaded_file) -> dict | None:
    """保存文件到 uploads/kb/{entry_id}/{uuid}.ext，写 kb_attachments 表"""

def get_attachments(entry_id) -> list[dict]:
    """查询某条目的所有附件"""

def get_attachment(att_id) -> dict | None:

def delete_attachment(att_id) -> bool:
    """删表记录 + 删磁盘文件，目录空则删目录"""

def _guess_mime(ext) -> str:
    """.pdf→application/pdf, .png→image/png, .docx→application/vnd... 等"""
```

**搜索 fallback 修复：** `search_entries()` 函数改为 FTS5 返回 0 条时自动切 LIKE 搜索：

```python
def search_entries(query, page=1, page_size=20):
    try:
        total, rows = _fts_search()   # FTS5 MATCH
        if total == 0:
            total, rows = _like_search()  # LIKE '%query%'
    except Exception:
        total, rows = _like_search()
```

### 2.3 修改文件：`knowledge_base/__init__.py`

导出新增：`add_attachment, get_attachments, get_attachment, delete_attachment`

### 2.4 修改文件：`pages/2_📚_知识库.py`

**新建条目表单：** 顶部 expander "➕ 新建知识条目"，包含标题、内容、分类、公开开关、多文件上传。创建后清空表单 (pop session keys)。

**条目列表显示附件：** 展开后标题旁显示 `📎N` 徽章，附件文件名列表。

**附件预览 helper 函数：**（定义在文件顶部，在 tab 渲染代码之前）

```python
FILE_ICONS = {"pdf":"📕","doc":"📘","docx":"📘","png":"🖼️","jpg":"🖼️",
              "xls":"📊","ppt":"📽️","mp3":"🎵","mp4":"🎬","zip":"📦", ...}

def _render_attachment(att):
    # 图片 mime.startswith("image/")：st.image() 显示
    # PDF：import fitz; 逐页 pixmap tobytes → st.image() 按页 tabs 显示
    # Word：import docx; 提取文本预览 → st.text_area
    # 文本 mime.startswith("text/")：直接读内容显示
    # 其他：显示图标+大小+下载按钮
```

**编辑弹窗也加文件上传。**

---

## 三、Agent 指挥中心大屏

### 3.1 新文件：`pages/10_🖥️_指挥中心.py`

深色 NASA 控制中心风格。布局：

```
┌─────────────────────────────────────────────┐
│  🖥️ GESHI 智能体指挥中心        14:32:08    │
│                             ALL SYSTEMS OK  │
├──────┬──────┬──────┬──────┬────────────────┤
│ 在线 │ 今日 │ Token│ 调用 │ 系统健康度     │
│Agent│ 任务 │ 消耗 │ 次数 │ 99.8%          │
│  7  │  12  │ 2.3k │  156 │                │
├──────┴──────┴──────┴──────┴────────────────┤
│   📜 Agent 活动日志     │  📊 Agent 性能排行 │
│   14:30:01 协调智能体..│  协调 ████████ 12次│
│   14:30:02 任务智能体..│  知识 ████ 5次     │
│                        │  ⏱ 响应时间排行    │
├────────────────────────┴────────────────────┤
│  💬 快速指令 [输入...              ] [执行] │
└─────────────────────────────────────────────┘
```

**统计卡片 CSS：** `.war-stat-card` — 暗底 `rgba(15,23,42,0.9)`，顶部渐变线，`backdrop-filter: blur`，数值用 `background-clip: text` 渐变色。

**数据来源：**
```python
from agent_core.memory import get_agent_activity_log, get_agent_stats
stats = get_agent_stats(user_id=user["id"])
logs = get_agent_activity_log(user_id=user["id"], limit=40)
```

**性能柱状图：** 纯 CSS，div 宽度百分比动态计算。

**侧边栏：** 自动刷新开关（5秒 st.rerun）。

---

## 四、新增 Agent 工具

### 4.1 公告工具：`agent_core/tools/announcement_tools.py`（新文件）

```python
def _create_announcement(title, content, user_id=0, is_pinned=False, **_):
    from announcements import create_announcement
    ann_id = create_announcement(title, content, user_id, is_pinned=is_pinned)
    return json.dumps({"success": True, "announcement_id": ann_id, ...})

def _list_announcements(limit=10, **_):
    from announcements import list_announcements
    ...
```

注册两个 ToolDef：`create_announcement`（domain="notification", requires_user_id=True）、`list_announcements`（domain="notification"）。

### 4.2 修改：`announcements/manager.py`

`create_announcement` 函数内，insert 后给所有用户的 notifications 表各插入一条 `type='system'` 的通知。

### 4.3 删除工具

在现有 tool 文件中加：

| 文件 | 新工具 | handler |
|---|---|---|
| `agent_core/tools/task_tools.py` | `delete_task` | `_delete_task(task_id)` 调 `tasks.delete_task` |
| `agent_core/tools/calendar_tools.py` | `delete_event` | `_delete_event(event_id)` 调 `scheduler.delete_event` |
| `agent_core/tools/general_tools.py` | `delete_approval` | `_delete_approval(approval_id, user_id)` 调 `approvals.delete_approval` |

### 4.4 KB 工具增强：`agent_core/tools/kb_tools.py`

**新增 `list_kb_entries`：** 调 `knowledge_base.list_entries`，返回含附件信息（`has_attachments`, `attachment_count`, `attachments` 数组）。

**新增 `get_entry_detail`：** 调 `knowledge_base.get_entry`，返回含完整内容和附件列表。

**所有条目列表附带附件信息：** 用统一的 `_entry_to_dict()` helper。

### 4.5 修改：`agent_core/coordinator.py`

在 `build_registry()` 里加：
```python
+ register_announcement_tools()
```

路由 prompt 加：
```
可用领域：... approval(审批), announcement(公告通知), general(通用)
```

### 4.6 修改：`agent_core/domain_agents.py`

通用助理 prompt 里加一行：
```
- 公告通知：发布系统公告、查看公告列表
```

---

## 五、活动日志 + 用户隔离

### 5.1 修改：`agent_core/memory.py`

**新增表：**
```sql
CREATE TABLE IF NOT EXISTS agent_activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT DEFAULT '',
    duration_ms INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    success INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

迁移：`ALTER TABLE agent_activity_log ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1`（try/except 忽略已存在错误）。

**新增函数：**
```python
def log_agent_activity(agent_name, action, detail="", duration_ms=0,
                       token_count=0, success=True, user_id=1):
    """写活动日志"""

def get_agent_activity_log(user_id=None, limit=50):
    """查活动日志，按 user_id 过滤"""

def get_agent_stats(user_id=None):
    """聚合统计：总操作数、今日操作、Token 消耗、Average 响应时间、按 agent 分组"""
    # 所有查询用参数化 SQL，参数用 ? 占位符
```

### 5.2 调用处修改

`pages/0_🤖_智能助手.py` 每次请求后调用：
```python
log_agent_activity("协调智能体", "handle_request",
                   user_input[:80], int(total_elapsed * 1000), total_tokens_est,
                   user_id=user["id"])
```

`pages/10_🖥️_指挥中心.py` 快速指令后调用同。

**指挥中心页面所有查询都带 `user_id=user["id"]`。**

---

## 六、其他页面修复

### 6.1 仪表盘实时数据：`app.py`

简报数据缓存（一天一次），但未读通知和待审批数字每次实时查：
```python
live_notif_unread = get_unread_notif_count(user["id"])
live_pending_approvals = conn.execute(
    "SELECT COUNT(*) FROM approvals WHERE current_approver_id=? AND status='pending'",
    (user["id"],)
).fetchone()[0]
```

加 `from database import get_connection` 导入。

简报加「🔄 刷新」按钮，点击清缓存重新生成。

### 6.2 日程管理：`pages/6_📅_日程管理.py`

- 日历格子：`st.button(day, key=f"day_{y}_{m}_{d}")` 替代 markdown
- 选中日期存在 `st.session_state["selected_day"]`
- 左侧显示选中日期的日程，每条有 ✏️ 编辑 / 🗑️ 删除按钮
- 编辑模式：标题和描述可修改

### 6.3 审批管理：`pages/5_📋_审批管理.py`

- 审批历史 tab：加下拉框 "我的申请" / "我审批的"
- "我的申请" → `list_approvals(applicant_id=user["id"], status=...)`
- "我审批的" → `list_approvals(involved_user_id=user["id"], status=...)`
- 已完成/已驳回的申请旁加「🗑️ 删除」按钮

### 6.4 审批后端：`approvals/manager.py`

新增 `delete_approval(approval_id, user_id)` — 校验申请人身份后删除。

`list_approvals` 新增参数 `involved_user_id` — 匹配 `applicant_id` 或 `approval_chain LIKE '%user_id%'`。

---

## 七、.gitignore

```
data/*.db
uploads/
```

---

## 实现顺序建议

1. **先做无依赖的：** 活动日志表 + log_agent_activity + 用户隔离（只改 memory.py）
2. **再做数据库相关：** kb_attachments 表 + 附件 CRUD（connection.py + knowledge_base/manager.py）
3. **Agent 工具：** announcement_tools + delete 工具 + kb_tools 增强 + coordinator 注册
4. **前端页面：** 知识库 → 日程管理 → 审批管理 → 智能助手 → 指挥中心
5. **流式 + 推理面板：** llm_streaming.py → llm_client 加方法 → thinking_panel 重写 → 智能助手打字机
6. **仪表盘修复：** app.py 缓存 + 实时数据

每个模块做完都可以独立验证，不需要等全部完成。
