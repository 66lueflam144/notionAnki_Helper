# Notion Anki Helper

一个基于 Notion API 的自动化学习规划工具，该工具能够从 Notion 数据库中获取 Quiz 和回顾日志数据，根据 Anki 算法智能调整复习时间，并自动生成每日或未来多天的学习计划和待办事项。
主要是懒得手动一个一个弄……

比较重要的是关于notion数据库中页面的模板结构的提取

## 项目结构

```
.
├── main.py                     # CLI 入口文件，提供交互式命令行界面
├── requirements.txt            # 项目依赖库列表
├── README.md                   # 项目说明文档
├── cli/                        # 命令行界面相关模块
│   └── ui.py                   # 负责 CLI 的美观输出，如欢迎横幅
├── config/                     # 配置相关模块
│   ├── settings.py             # 项目设置，如 Notion API Key、数据库ID、日志配置等
│   └── __init__.py
├── core/                       # 核心业务逻辑模块
│   ├── daily_planner.py        # 每日/周期学习计划生成逻辑
│   ├── data_parser.py          # Notion API 返回数据解析工具
│   └── notion_client_wrapper.py# Notion API 客户端封装
├── data/                       # 存储数据库ID等运行时数据
├── model/                      # 存储 Notion 数据库的属性模型（Schema）快照
├── scripts/                    # 独立脚本，可被 CLI 调用
│   ├── anki_scheduler.py       # Anki 调度算法实现，负责更新 Quiz 回顾时间
│   ├── extract_model_from_pages.py # 从 Notion 页面数据中提取数据库模型
│   ├── fetch_n_parse_db.py     # 获取并解析 Notion 数据库页面数据
│   └── generate_daily_plan.py  # 每日计划生成脚本（现在主要由 core/daily_planner 调用）
└── utils/                      # 通用工具函数
    └── helper.py               # 辅助函数，如属性格式化
```

## 技术栈

*   **Python 3.x**: 主要开发语言。
*   **Notion API**: 用于与 Notion 数据库进行交互。
*   **`notion-client`**: Notion 官方 Python 客户端库。
*   **`python-dotenv`**: 用于从 `.env` 文件加载环境变量，管理敏感信息。
*   **`rich`**: 用于创建美观、彩色的终端输出和交互式界面。
*   **`pyfiglet`**: 用于生成 ASCII 艺术字体，美化 CLI 横幅。
*   **`argparse`**: Python 标准库，用于解析命令行参数。
*   **`logging`**: Python 标准库，用于日志记录。

## 用法

### 1. 环境准备

1.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **配置 Notion API**:
    *   在项目根目录下创建 `.env` 文件。
    *   获取您的 Notion API Key 和相关数据库 ID。
    *   在 `.env` 文件中添加以下内容，替换为您的实际值：
        ```
        NOTION_API_KEY="secret_YOUR_NOTION_API_KEY"
        DATABASE_IDS="your_quiz_db_id,your_study_plan_db_id,your_todo_db_id,your_review_log_db_id"
        # 例如：DATABASE_IDS="a1b2c3d4-e5f6-7890-1234-567890abcdef,..."
        ```
        请确保 `DATABASE_IDS` 包含 `Quiz库`, `学习计划`, `Todo库`, `Quiz回顾日志` 等数据库的 ID，并用逗号分隔。

3.  **Notion 数据库设置**:
    *   确保 `Quiz回顾日志` 数据库中包含一个名为 `是否已处理` 的 `Checkbox` 属性。

### 2. 运行工具

通过运行 `main.py` 脚本来启动交互式命令行界面：

```bash
python main.py
```

启动后，可以看到一个欢迎横幅和命令行提示符 `>>>`。

### 3. 可用命令

在 `>>>` 提示符后输入以下命令：

*   **`help`**:
    显示所有可用命令的帮助信息。

*   **`plan-daily`**:
    生成当天的学习计划和待办事项。该命令会根据预设规则（最少2科目各2Quiz，最多3科目各1Quiz）从即将到期的 Quiz 中选择任务。

*   **`plan-period --days <N>`**:
    为未来 N 天生成学习计划和待办事项。例如，`plan-period --days 3` 将规划未来三天的学习任务。工具会智能分配任务，避免重复。

*   **`update-quiz <review_log_page_id>`**:
    根据指定的 Quiz 回顾日志页面 ID，更新其关联 Quiz 的下次回顾时间。该命令会根据回顾效果和回顾次数重新计算复习间隔。

*   **`process-reviews`**:
    批量处理所有在 Notion 中“未被处理”的 Quiz 回顾日志。该命令会自动查找所有未勾选“是否已处理”的日志，逐一更新关联 Quiz 的复习时间，并标记日志为“已处理”。

*   **`won`**:
    退出交互式命令行界面。

### 4. 日志输出

工具的日志输出已通过 `rich` 库美化，提供彩色和结构化的信息，方便您跟踪程序运行状态和调试。

## 参考

- [notion database and properties](https://developers.notion.com/reference/property-object)
- [notion integration](https://developers.notion.com/reference/capabilities)
- [How to Study for Exams An Evidence Based Masterclass](https://youtu.be/Lt54CX9DmS4?feature=shared)
