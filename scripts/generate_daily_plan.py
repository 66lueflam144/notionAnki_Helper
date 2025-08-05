
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from config.settings import settings

from core.data_parser import parse_page_property_value
from core.notion_client_wrapper import NotionManager
from utils.helper import format_property_for_create

# 配置日志
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 当前科目列表
CURRENT_SUBJECTS = settings.CURRENT_SUBJECTS

def load_database_ids():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    ids_file_path = os.path.join(project_root, "data", "database_ids.json")

    try:
        with open(ids_file_path, 'r', encoding='utf-8') as f:
            db_ids = json.load(f)
        logger.info(f"[✓] Loaded database IDs from {ids_file_path}")
        return db_ids
    except FileNotFoundError:
        logger.error(f"[x] Database IDs file not found: {ids_file_path}")
    except json.JSONDecodeError as e:
        logger.error(f"[x] Error decoding JSON from {ids_file_path}: {e}")
    except Exception as e:
        logger.error(f"[x] Unexpected error loading {ids_file_path}: {e}")
    return None

def get_upcoming_quizzes(notion_manager, quiz_db_id, days_ahead=7):
    """
    从 Quiz库 查询即将到期的 Quiz。
    :param notion_manager: NotionManager 实例
    :param quiz_db_id: Quiz库的数据库ID
    :param days_ahead: 查询未来多少天内的 Quiz
    :return: Quiz 页面数据列表
    """
    logger.info(f"Fetching quizzes due in the next {days_ahead} days...")

    # 计算查询日期范围
    today = datetime.utcnow().date()
    end_date = today + timedelta(days=days_ahead)

    # 构建 Notion API filter
    # 过滤 '下次回顾时间' 在 [today, end_date] 范围内
    filter_obj = {
        "property": "下次回顾时间",  # 属性名
        "date": {
            "on_or_after": today.isoformat(),  # API 通常接受 YYYY-MM-DD 格式
            "on_or_before": end_date.isoformat()
        }
    }

    quizzes = []
    try:
        # 使用 query_database 获取页面
        for page in notion_manager.query_database(quiz_db_id, filter_=filter_obj):
            quizzes.append(page)
        logger.info(f"Found {len(quizzes)} quizzes due soon.")
        return quizzes
    except Exception as e:
        logger.error(f"Error querying upcoming quizzes: {e}")
        return []


def aggregate_quizzes_by_subject_and_chapter(quizzes):
    """
    将 Quiz 按科目和章节聚合。
    :param quizzes: Quiz 页面数据列表
    :return: 聚合后的字典 {subject: {chapter: [quiz_page_obj, ...]}}
    """
    logger.info("Aggregating quizzes by subject and chapter...")
    aggregated = {}

    for quiz_page in quizzes:
        props = quiz_page.get("properties", {})

        # 解析 '所属课程' (Select)
        course_prop_obj = props.get("所属课程", {})
        subject = parse_page_property_value(course_prop_obj)  # 应该是字符串或 None

        # 解析 '章节/关键词' (Multi-Select)
        chapter_prop_obj = props.get("章节/关键词", {})
        chapters = parse_page_property_value(chapter_prop_obj)  # 应该是字符串列表或 []

        # 解析 '下次回顾时间' (Date) - 用于排序或进一步分析 (可选)
        # next_review_prop_obj = props.get("下次回顾时间", {})
        # next_review_date = parse_page_property_value(next_review_prop_obj) # 字符串或 None

        if not subject or not chapters:
            logger.warning(f"Quiz page {quiz_page.get('id')} missing '所属课程' or '章节/关键词'. Skipping.")
            continue

        if subject not in CURRENT_SUBJECTS:
            logger.info(
                f"Quiz page {quiz_page.get('id')} belongs to subject '{subject}' which is not in the current list. Skipping.")
            continue

        # 初始化科目
        if subject not in aggregated:
            aggregated[subject] = {}

        # 为每个章节添加 Quiz
        for chapter in chapters:
            if chapter not in aggregated[subject]:
                aggregated[subject][chapter] = []
            aggregated[subject][chapter].append(quiz_page)

    logger.info(f"Aggregation complete. Subjects found: {list(aggregated.keys())}")
    return aggregated


def select_daily_subjects_and_chapters(aggregated_data):
    """
    选择每日要学习的两个科目和至少两个章节。
    策略：选择有最多不同章节的两个科目。
    :param aggregated_data: 聚合后的数据 {subject: {chapter: [quiz_page_obj, ...]}}
    :return: (selected_subjects_list, selected_chapters_dict)
             selected_chapters_dict: {subject: [chapter1, chapter2, ...]}
    """
    logger.info("Selecting daily subjects and chapters...")

    if not aggregated_data:
        logger.warning("No aggregated quiz data available for selection.")
        return [], {}

    # 按科目下不同章节数量排序
    subject_chapter_counts = {subj: len(chaps) for subj, chaps in aggregated_data.items()}
    sorted_subjects = sorted(subject_chapter_counts.keys(), key=lambda s: subject_chapter_counts[s], reverse=True)

    selected_subjects = []
    selected_chapters = {}

    # 选择两个科目
    for subject in sorted_subjects[:2]:
        selected_subjects.append(subject)
        # 选择该科目下的所有章节 (或可以限制数量)
        # 这里简单选择所有找到的章节
        chapters = list(aggregated_data[subject].keys())
        selected_chapters[subject] = chapters
        logger.info(f"Selected subject '{subject}' with chapters: {chapters}")

    # 确保至少有两个不同的章节被选中
    all_selected_chapters = []
    for chaps in selected_chapters.values():
        all_selected_chapters.extend(chaps)

    unique_selected_chapters = list(set(all_selected_chapters))  # 去重

    if len(unique_selected_chapters) < 2:
        logger.warning(
            f"Selected subjects only provide {len(unique_selected_chapters)} unique chapters, less than required 2.")
        # 可以尝试选择更多科目或章节，这里简单处理
        # ... (可以添加更复杂的逻辑)

    logger.info(f"Final selection: Subjects {selected_subjects}, Unique Chapters {unique_selected_chapters}")
    return selected_subjects, selected_chapters


def create_study_plan_and_todos(notion_manager, selected_subjects, selected_chapters, study_plan_schema, todo_schema, study_plan_db_id, todo_db_id):
    """
    创建学习计划和 Todo 任务。
    :param notion_manager: NotionManager 实例
    :param selected_subjects: 选中的科目列表
    :param selected_chapters: 选中的章节字典 {subject: [chapter, ...]}
    :param study_plan_schema: 学习计划数据库的 schema
    :param todo_schema: Todo库数据库的 schema
    :param study_plan_db_id: 学习计划数据库id
    :param todo_db_id: `TODO`库数据库id
    """
    logger.info("Creating Study Plan and Todo items...")
    today_str = datetime.utcnow().date().isoformat()
    plan_title = f"每日学习计划 - {today_str}"

    # --- 1. 创建 学习计划 条目 ---
    try:
        study_plan_props = {}
        # '关键词' (Title)
        title_schema = study_plan_schema.get("properties", {}).get("关键词", {})
        if title_schema:
            study_plan_props["关键词"] = {"title": format_property_for_create(title_schema, plan_title)}

        # 'Date' (Date)
        date_schema = study_plan_schema.get("properties", {}).get("Date", {})
        if date_schema:
            study_plan_props["Date"] = {"date": format_property_for_create(date_schema, today_str)}

        # '科目' (Multi-Select)
        subject_schema = study_plan_schema.get("properties", {}).get("科目", {})
        if subject_schema:
            # 将列表转换为逗号分隔的字符串
            subjects_str = ",".join(selected_subjects)
            if not all(s in CURRENT_SUBJECTS for s in selected_subjects):
                logger.warning(f"Some selected subjects {selected_subjects} are not in the configured CURRENT_SUBJECTS list.")
            study_plan_props["科目"] = {"multi_select": format_property_for_create(subject_schema, subjects_str)}

        # '是否含quiz' (Checkbox) - 假设为 True
        quiz_checkbox_schema = study_plan_schema.get("properties", {}).get("是否含quiz", {})
        if quiz_checkbox_schema:
            study_plan_props["是否含quiz"] = {"checkbox": format_property_for_create(quiz_checkbox_schema, "true")}

        # '学习状态' (Select) - 假设为 "TODO"
        status_schema = study_plan_schema.get("properties", {}).get("学习状态", {})
        if status_schema:
            status_to_set = "TODO"
            if status_to_set not in settings.QUIZ_LEARNING_STATES:
                logger.warning(f"Status '{status_to_set}' might not be a valid option for Study Plan '学习状态'.")
            study_plan_props["学习状态"] = {"select": format_property_for_create(status_schema, "TODO")}

        logger.debug(f"Study Plan page properties to create: {json.dumps(study_plan_props, indent=2, ensure_ascii=False)}")
        # 创建页面
        study_plan_page = notion_manager.create_page(study_plan_db_id, study_plan_props)
        study_plan_page_id = study_plan_page["id"]
        logger.info(f"Created Study Plan page with ID: {study_plan_page_id}")

    except Exception as e:
        logger.error(f"Error creating Study Plan page: {e}")
        return  # 如果学习计划创建失败，可能不继续创建 Todo

    # --- 2. 创建 Todo库 条目 ---
    todo_count = 0
    try:
        # 遍历选中的科目和章节来创建 Todo
        for subject, chapters in selected_chapters.items():
            for chapter in chapters:
                todo_title = f"复习 {chapter} - {subject}"
                todo_props = {}

                # 'ToDo名称' (Title)
                todo_title_schema = todo_schema.get("properties", {}).get("ToDo名称", {})
                if todo_title_schema:
                    todo_props["ToDo名称"] = {"title": format_property_for_create(todo_title_schema, todo_title)}

                # '科目' (Select)
                todo_subject_schema = todo_schema.get("properties", {}).get("科目", {})
                if todo_subject_schema:
                    todo_props["科目"] = {"select": format_property_for_create(todo_subject_schema, subject)}

                # '预计完成时间' (Date)
                due_date_schema = todo_schema.get("properties", {}).get("预计完成时间", {})
                if due_date_schema:
                    todo_props["预计完成时间"] = {"date": format_property_for_create(due_date_schema, today_str)}

                # '关联计划' (Relation) - 指向刚创建的学习计划
                relation_schema = todo_schema.get("properties", {}).get("关联计划", {})
                if relation_schema:
                    # Relation 需要页面 ID 列表
                    relation_value = format_property_for_create(relation_schema, study_plan_page_id)
                    todo_props["关联计划"] = {"relation": relation_value}
                else:
                    logger.warning(f"Failed to format relation for Todo item.")


                # '任务类型' (Multi-Select) - 示例
                task_type_schema = todo_schema.get("properties", {}).get("任务类型", {})
                if task_type_schema:
                    task_types_str = "学习,Quiz"  # 逗号分隔
                    todo_props["任务类型"] = {
                        "multi_select": format_property_for_create(task_type_schema, task_types_str)}

                logger.debug(f"Todo page properties to create for '{todo_title}': {json.dumps(todo_props, indent=2, ensure_ascii=False)}")
                # 创建 Todo 页面
                notion_manager.create_page(todo_db_id, todo_props)
                logger.info(f"Created Todo page for '{todo_title}'")
                todo_count += 1

    except Exception as e:
        logger.error(f"Error creating Todo pages: {e}")

    logger.info(f"Finished creating plan. Created {todo_count} Todo items.")


def main():
    """主函数"""
    logger.info("Starting daily plan generation process...")

    db_ids = load_database_ids()
    if not db_ids:
        logger.error("Failed to load database IDs. Exiting.")
        sys.exit(1)

    try:
        # 直接从 db_ids 字典中获取，如果键不存在会抛出 KeyError
        QUIZ_DB_ID = db_ids["Quiz库"]
        STUDY_PLAN_DB_ID = db_ids["学习计划"]
        TODO_DB_ID = db_ids["Todo库"]
    except KeyError as e:
        logger.error(
            f"Required database title not found in database_ids.json: {e}. Please check the keys match your database titles exactly.")
        sys.exit(1)

    if not all([QUIZ_DB_ID, STUDY_PLAN_DB_ID, TODO_DB_ID]):
        logger.error("One or more database IDs are missing or invalid.")
        sys.exit(1)

    if not all([QUIZ_DB_ID, STUDY_PLAN_DB_ID, TODO_DB_ID]):
        missing = []
        if not QUIZ_DB_ID: missing.append("'Quiz库'")
        if not STUDY_PLAN_DB_ID: missing.append("'学习计划'")
        if not TODO_DB_ID: missing.append("'Todo库'")
        logger.error(f"Missing database IDs in database_ids.json for: {', '.join(missing)}")
        sys.exit(1)

    notion_manager = NotionManager()

    # 1. 获取数据库 Schema (用于格式化属性)
    try:
        study_plan_schema = notion_manager.retrieve_database(STUDY_PLAN_DB_ID)
        todo_schema = notion_manager.retrieve_database(TODO_DB_ID)
    except Exception as e:
        logger.error(f"Failed to retrieve database schemas: {e}")
        sys.exit(1)

    # 2. 获取即将到来的 Quiz
    upcoming_quizzes = get_upcoming_quizzes(notion_manager, QUIZ_DB_ID)

    if not upcoming_quizzes:
        logger.info("No upcoming quizzes found. Exiting.")
        return

    # 3. 聚合 Quiz 数据
    aggregated_data = aggregate_quizzes_by_subject_and_chapter(upcoming_quizzes)

    if not aggregated_data:
        logger.info("No quizzes could be aggregated. Exiting.")
        return

    # 4. 选择每日科目和章节
    selected_subjects, selected_chapters = select_daily_subjects_and_chapters(aggregated_data)

    if not selected_subjects:
        logger.info("No subjects selected. Exiting.")
        return

    # 5. 创建计划和任务
    create_study_plan_and_todos(notion_manager, selected_subjects, selected_chapters, study_plan_schema, todo_schema, STUDY_PLAN_DB_ID, TODO_DB_ID)

    logger.info("Daily plan generation process completed.")


if __name__ == "__main__":
    main()
