# Geshi 智能办公系统

基于多智能体的智能办公平台，集成语音转写、结构化总结、知识库管理。

## 功能

### 已实现（Phase 1）
- **用户认证**：注册 / 登录 / 角色管理（管理员 / 普通用户）
- **语音转文本结构化总结**：
  - 文本粘贴与 TXT/DOCX 上传
  - 阿里云 Paraformer 语音识别
  - 文本清洗、场景识别（会议/课堂/混合/通用）
  - 会议纪要、课堂知识提炼
  - 质量校验与导出（Markdown/Word/PDF）
- **知识库**：
  - 分类管理、标签系统
  - 全文搜索（FTS5）
  - 从总结一键导入
  - 权限控制（公开/私有）

### 规划中
- Phase 2：任务管理 + 通知系统
- Phase 3：审批流 + 日程管理
- Phase 4：考勤 + 公告 + IM

## 运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动
streamlit run app.py
```

浏览器打开 Streamlit 输出的本地地址即可使用。

## 默认账户

- 管理员：`admin` / `admin123`
- 首次登录后建议修改密码

## 配置

复制 `.env.example` 为 `.env`，按需填入 API Key：

### DeepSeek LLM（可选，无配置时使用本地规则引擎）

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的DeepSeek_API_KEY
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_TEMPERATURE=0.2
LLM_TIMEOUT=90
```

### 阿里云语音识别（可选）

```env
DASHSCOPE_API_KEY=你的阿里云百炼API_KEY
ASR_MODEL=paraformer-8k-v1
ASR_BASE_URL=https://dashscope.aliyuncs.com/api/v1
ASR_POLL_INTERVAL=3
ASR_TIMEOUT=600
ASR_DISFLUENCY_REMOVAL=true
ASR_DIARIZATION=false
```

### 架构

```
geshi_demo/
├── app.py                  # 主入口（登录/仪表盘）
├── auth/                   # 认证模块
│   └── manager.py
├── database/               # 数据库模块（SQLite）
│   └── connection.py
├── knowledge_base/         # 知识库模块
│   └── manager.py
├── pages/                  # Streamlit 子页面
│   ├── 1_📝_语音总结.py
│   ├── 2_📚_知识库.py
│   └── 3_👥_用户管理.py
├── summary_system/         # 总结引擎（多智能体）
│   ├── agents.py           # 智能体编排
│   ├── llm_client.py       # LLM 客户端
│   ├── asr_client.py       # 语音识别客户端
│   ├── models.py           # 数据模型
│   ├── text_utils.py       # 文本处理
│   ├── exporters.py        # 多格式导出
│   └── archive.py          # 归档管理
└── data/                   # 运行时数据
    ├── geshi.db            # SQLite 数据库
    ├── archive/            # 总结归档
    └── exports/            # 导出文件
```
