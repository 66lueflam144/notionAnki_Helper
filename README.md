# Notion Anki Helper

一个用于管理我自己的 Notion 数据库的工具。对于数据库中的页面进行数据收集、模板提取，创建、删除、修改页面。

## 项目结构

```
.
├── main.py                     # CLI 入口文件，提供交互式命令行界面。
├── requirements.txt            # 项目依赖库列表。
├── README.md                   # 项目说明文档。
├── cli/                        # 命令行界面相关模块。
│   └── ui.py                   # 负责 CLI 的美观输出。
├── config/                     # 配置相关模块。
│   ├── settings.py             # 项目设置，如 Notion API Key、数据库ID、日志配置等。
│   └── __init__.py
├── core/                       # 核心业务逻辑模块。
│   ├── ai_service.py           # AI 服务，与大模型交互，用于评估和内容生成。
│   ├── daily_planner.py        # 每日/周期学习计划生成逻辑。
│   ├── data_parser.py          # Notion API 返回数据解析工具。
│   └── notion_client_wrapper.py# Notion API 客户端封装。
├── data/                       # 存储数据库ID等运行时数据。
├── model/                      # 存储 Notion 数据库的属性模型（Schema）快照。
├── scripts/                    # 独立脚本，可被 CLI 调用。
│   ├── anki_scheduler.py       # Anki 调度算法实现，负责更新 Quiz 回顾时间。
│   ├── extract_model_from_pages.py # 从 Notion 页面数据中提取数据库模型。
│   ├── fetch_n_parse_db.py     # 获取并解析 Notion 数据库页面数据。
│   └── generate_daily_plan.py  # 每日计划生成脚本。
└── utils/                      # 通用工具函数。
    └── helper.py               # 辅助函数，如属性格式化。
```

## 技术栈

*   **Python 3.10+**: 主要开发语言。
*   **Notion API**: 用于与 Notion 数据库进行交互。
*   **`notion-client`**: Notion 官方 Python 客户端库。
*   **`python-dotenv`**: 用于从 `.env` 文件加载环境变量。
*   **`rich`**: 用于创建美观、彩色的终端输出。
*   **`pyfiglet`**: 用于生成 ASCII 艺术字体。
*   **`openai`**: 兼容 DeepSeek API，用于与大模型交互。
*   **`google-generativeai`**: （可选）用于与 Gemini API 交互。
*   **`argparse`**: Python 标准库，用于解析命令行参数。
*   **`logging`**: Python 标准库，用于日志记录。

## 用法

### 1. 环境准备


1.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **配置 Notion & AI API**:
    *   在项目根目录下创建 `.env` 文件。
    *   获取 Notion API Key 、AI API KEY和相关数据库 ID。
    *   在 `.env` 文件中添加以下内容，替换为实际值：
        ```
        NOTION_API_KEY="secret_YOUR_NOTION_API_KEY"
        DATABASE_IDS="your_quiz_db_id,your_study_plan_db_id,your_todo_db_id,your_review_log_db_id"
        # 例如：DATABASE_IDS="a1b2c3d4-e5f6-7890-1234-567890abcdef,..."
        DEEPSEEK_API_KEY="sk-YOUR_DEEPSEEK_API_KEY"
        # 如果使用 Gemini，也可以加上：
        # GEMINI_API_KEY="your_gemini_api_key"
        ```
        请确保 `DATABASE_IDS` 包含 `Quiz库`, `学习计划`, `Todo库`, `Quiz回顾日志` 等数据库的 ID，并用逗号分隔。

3.  **Notion 数据库设置**:
    *   确保 `Quiz回顾日志` 数据库中包含一个名为 `是否已处理` 的 `Checkbox` 属性。
    *   确保 `Quiz库` 数据库中包含一个名为 `参考答案` 的 `Rich Text` 属性。
    *   确保 `Quiz回顾日志` 数据库中包含 `AI评估结果` (Select 类型，选项如“正确”、“部分正确”、“错误”、“概念混淆”) 和 `AI反馈` (Rich Text 类型) 属性。

### 2. 运行工具

通过运行 `main.py` 脚本来启动交互式命令行界面：

```bash
python main.py
```

启动后，将看到欢迎信息和命令行提示符 `>>>`。

### 3. 可用命令

在 `>>>` 提示符后输入以下命令：

*   **`help`**:
    显示所有可用命令的帮助信息。

*   **`plan-daily`**:
    生成当天的学习计划和待办事项。

*   **`plan-period --days <N>`**:
    为未来 N 天生成学习计划和待办事项。

*   **`update-quiz <review_log_page_id>`**:
    根据指定的 Quiz 回顾日志页面 ID，更新其关联 Quiz 的下次回顾时间。

*   **`process-reviews`**:
    批量处理所有在 Notion 中“未被处理”的 Quiz 回顾日志。该命令会自动查找所有新完成的日志，调用 AI 对回答进行评估，给出详细反馈，然后更新关联 Quiz 的复习时间，并标记日志为“已处理”。请注意，一定要有参考答案，不然对比不了（目前实现的功能就这样）

*   **`won`**:
    退出交互式命令行界面。

### 4. 日志输出

日志输出已通过 `rich` 库美化，提供彩色和结构化的信息。

## 参考

-   [Notion Database and Properties](https://developers.notion.com/reference/property-object)
-   [Notion Integration](https://developers.notion.com/reference/capabilities)
-   [How to Study for Exams An Evidence Based Masterclass](https://youtu.be/Lt54CX9DmS4?feature=shared)
