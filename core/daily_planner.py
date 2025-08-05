import json
import logging
from datetime import datetime, timedelta

from config.settings import settings
from core.data_parser import parse_page_property_value
from core.notion_client_wrapper import NotionManager
from utils.helper import format_property_for_create

logger = logging.getLogger(__name__)

# 当前科目列表
CURRENT_SUBJECTS = settings.CURRENT_SUBJECTS


def get_upcoming_quizzes(notion_manager: NotionManager, quiz_db_id: str, days_ahead: int = 7):
    """
    从 Quiz库 查询即将到期的 Quiz。
    :param notion_manager: NotionManager 实例
    :param quiz_db_id: Quiz库的数据库ID
    :param days_ahead: 查询未来多少天内的 Quiz
    :return: Quiz 页面数据列表
    """
    logger.info(f"Fetching quizzes due in the next {days_ahead} days...")

    today = datetime.utcnow().date()
    end_date = today + timedelta(days=days_ahead)

    filter_obj = {
        "property": "下次回顾时间",
        "date": {
            "on_or_after": today.isoformat(),
            "on_or_before": end_date.isoformat()
        }
    }

    try:
        quizzes = list(notion_manager.query_database(quiz_db_id, filter_=filter_obj))
        logger.info(f"Found {len(quizzes)} quizzes due soon.")
        return quizzes
    except Exception as e:
        logger.error(f"Error querying upcoming quizzes: {e}")
        return []


def aggregate_quizzes_by_subject_and_chapter(quizzes: list):
    """
    将 Quiz 按科目和章节聚合。
    :param quizzes: Quiz 页面数据列表
    :return: 聚合后的字典 {subject: {chapter: [quiz_page_obj, ...]}}
    """
    logger.info("Aggregating quizzes by subject and chapter...")
    aggregated = {}

    for quiz_page in quizzes:
        props = quiz_page.get("properties", {})
        subject = parse_page_property_value(props.get("所属课程", {}))
        chapters = parse_page_property_value(props.get("章节/关键词", {}))

        if not subject or not chapters:
            logger.warning(f"Quiz page {quiz_page.get('id')} missing '所属课程' or '章节/关键词'. Skipping.")
            continue

        if subject not in CURRENT_SUBJECTS:
            logger.info(f"Quiz page {quiz_page.get('id')} belongs to subject '{subject}' which is not in the current list. Skipping.")
            continue

        if subject not in aggregated:
            aggregated[subject] = {}

        for chapter in chapters:
            if chapter not in aggregated[subject]:
                aggregated[subject][chapter] = []
            aggregated[subject][chapter].append(quiz_page)

    logger.info(f"Aggregation complete. Subjects found: {list(aggregated.keys())}")
    return aggregated


def select_daily_quizzes(quizzes: list, min_subjects=2, max_subjects=3, min_quizzes_per_subject=2, max_quizzes_total=6):
    """
    根据规则选择每日要复习的 Quiz。
    :param quizzes: 待复习的 Quiz 列表。
    :return: (selected_subjects_list, selected_quizzes_dict)
    """
    logger.info("Selecting daily quizzes based on new rules...")

    if not quizzes:
        logger.warning("No quizzes available for selection.")
        return [], {}

    # 1. 按科目分组
    quizzes_by_subject = {}
    for quiz in quizzes:
        subject = parse_page_property_value(quiz["properties"].get("所属课程", {}))
        if subject not in quizzes_by_subject:
            quizzes_by_subject[subject] = []
        quizzes_by_subject[subject].append(quiz)

    # 2. 科目评分和排序 (简化版：按待复习数量排序)
    #    未来可以加入更多维度：回顾时间、回顾效果等
    sorted_subjects = sorted(quizzes_by_subject.keys(), key=lambda s: len(quizzes_by_subject[s]), reverse=True)

    selected_quizzes_dict = {}
    selected_subjects_list = []
    total_quiz_count = 0

    # 3. 迭代选择
    for subject in sorted_subjects:
        if len(selected_subjects_list) >= max_subjects:
            break

        quizzes_for_subject = quizzes_by_subject[subject]
        
        # 尝试满足最少要求
        if len(selected_subjects_list) < min_subjects:
            num_to_select = min(len(quizzes_for_subject), min_quizzes_per_subject)
            if total_quiz_count + num_to_select > max_quizzes_total:
                continue
            
            selected_quizzes_dict[subject] = quizzes_for_subject[:num_to_select]
            selected_subjects_list.append(subject)
            total_quiz_count += num_to_select
        else: # 已满足最少科目数，尝试添加更多
            num_to_select = 1
            if total_quiz_count + num_to_select > max_quizzes_total:
                continue

            selected_quizzes_dict[subject] = quizzes_for_subject[:num_to_select]
            selected_subjects_list.append(subject)
            total_quiz_count += num_to_select

    logger.info(f"Final selection: {len(selected_subjects_list)} subjects, {total_quiz_count} quizzes.")
    logger.info(f"Selected subjects: {selected_subjects_list}")
    
    # 将 quiz 对象转换为 chapter 字典以适应现有函数
    selected_chapters_dict = {}
    for subject, quiz_list in selected_quizzes_dict.items():
        chapters = set()
        for quiz in quiz_list:
            quiz_chapters = parse_page_property_value(quiz["properties"].get("章节/关键词", {}))
            if quiz_chapters:
                chapters.update(quiz_chapters)
        selected_chapters_dict[subject] = list(chapters)

    return selected_subjects_list, selected_chapters_dict


def create_study_plan_and_todos(notion_manager: NotionManager, selected_subjects: list, selected_chapters: dict, study_plan_db_id: str, todo_db_id: str):
    """
    创建学习计划和 Todo 任务。
    """
    logger.info("Creating Study Plan and Todo items...")
    if not selected_subjects:
        logger.warning("No subjects selected, cannot create study plan.")
        return

    try:
        study_plan_schema = notion_manager.retrieve_database(study_plan_db_id)
        todo_schema = notion_manager.retrieve_database(todo_db_id)
    except Exception as e:
        logger.error(f"Failed to retrieve database schemas: {e}")
        return

    today_str = datetime.utcnow().date().isoformat()
    plan_title = f"每日学习计划 - {today_str}"
    study_plan_page_id = None

    # --- 1. 创建 学习计划 条目 ---
    try:
        study_plan_props = {}
        # '关键词' (Title)
        title_schema = study_plan_schema.get("properties", {}).get("关键词", {})
        study_plan_props["关键词"] = {"title": format_property_for_create(title_schema, plan_title)}

        # 'Date' (Date)
        date_schema = study_plan_schema.get("properties", {}).get("Date", {})
        study_plan_props["Date"] = {"date": format_property_for_create(date_schema, today_str)}

        # '科目' (Multi-Select)
        subject_schema = study_plan_schema.get("properties", {}).get("科目", {})
        subjects_str = ",".join(selected_subjects)
        study_plan_props["科目"] = {"multi_select": format_property_for_create(subject_schema, subjects_str)}

        # '是否含quiz' (Checkbox)
        quiz_checkbox_schema = study_plan_schema.get("properties", {}).get("是否含quiz", {})
        study_plan_props["是否含quiz"] = {"checkbox": format_property_for_create(quiz_checkbox_schema, "true")}

        # '学习状态' (Select)
        status_schema = study_plan_schema.get("properties", {}).get("学习状态", {})
        study_plan_props["学习状态"] = {"select": format_property_for_create(status_schema, "TODO")}

        logger.debug(f"Study Plan page properties to create: {json.dumps(study_plan_props, indent=2, ensure_ascii=False)}")
        study_plan_page = notion_manager.create_page(study_plan_db_id, study_plan_props)
        study_plan_page_id = study_plan_page["id"]
        logger.info(f"Created Study Plan page with ID: {study_plan_page_id}")

    except Exception as e:
        logger.error(f"Error creating Study Plan page: {e}")
        return

    # --- 2. 创建 Todo库 条目 ---
    todo_count = 0
    try:
        for subject, chapters in selected_chapters.items():
            for chapter in chapters:
                todo_title = f"复习 {chapter} - {subject}"
                todo_props = {}

                # 'ToDo名称' (Title)
                todo_title_schema = todo_schema.get("properties", {}).get("ToDo名称", {})
                todo_props["ToDo名称"] = {"title": format_property_for_create(todo_title_schema, todo_title)}

                # '科目' (Select)
                todo_subject_schema = todo_schema.get("properties", {}).get("科目", {})
                todo_props["科目"] = {"select": format_property_for_create(todo_subject_schema, subject)}

                # '预计完成时间' (Date)
                due_date_schema = todo_schema.get("properties", {}).get("预计完成时间", {})
                todo_props["预计完成时间"] = {"date": format_property_for_create(due_date_schema, today_str)}

                # '关联计划' (Relation)
                relation_schema = todo_schema.get("properties", {}).get("关联计划", {})
                relation_value = format_property_for_create(relation_schema, study_plan_page_id)
                todo_props["关联计划"] = {"relation": relation_value}

                # '任务类型' (Multi-Select)
                task_type_schema = todo_schema.get("properties", {}).get("任务类型", {})
                task_types_str = "学习,复习"
                todo_props["任务类型"] = {"multi_select": format_property_for_create(task_type_schema, task_types_str)}

                logger.debug(f"Todo page properties to create for '{todo_title}': {json.dumps(todo_props, indent=2, ensure_ascii=False)}")
                notion_manager.create_page(todo_db_id, todo_props)
                logger.info(f"Created Todo page for '{todo_title}'")
                todo_count += 1

    except Exception as e:
        logger.error(f"Error creating Todo pages: {e}")

    logger.info(f"Finished creating plan. Created {todo_count} Todo items.")
