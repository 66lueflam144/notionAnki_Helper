import json
import logging
from datetime import datetime, timedelta
import os
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
    :return: (selected_subjects_list, selected_chapters_dict, selected_quiz_ids)
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
    selected_quiz_ids = set()
    for subject, quiz_list in selected_quizzes_dict.items():
        chapters = set()
        for quiz in quiz_list:
            selected_quiz_ids.add(quiz["id"])
            quiz_chapters = parse_page_property_value(quiz["properties"].get("章节/关键词", {}))
            if quiz_chapters:
                chapters.update(quiz_chapters)
        selected_chapters_dict[subject] = list(chapters)

    return selected_subjects_list, selected_chapters_dict, selected_quiz_ids


def create_study_plan_and_todos(notion_manager: NotionManager, selected_subjects: list, selected_chapters: dict, study_plan_db_id: str, todo_db_id: str, plan_date: datetime.date):
    """
    创建学习计划和 Todo 任务, 并避免重复创建。
    :param plan_date: The specific date for which to create the plan.
    """
    logger.info(f"Attempting to create Study Plan and Todos for {plan_date.isoformat()}...")
    plan_date_str = plan_date.isoformat()

    # 1. 检查是否已存在当天的学习计划
    try:
        existing_plan_filter = {
            "property": "Date",
            "date": {
                "equals": plan_date_str
            }
        }
        existing_plans = list(notion_manager.query_database(study_plan_db_id, filter_=existing_plan_filter))
        if existing_plans:
            logger.warning(f"A study plan for {plan_date_str} already exists. Skipping creation.")
            return
    except Exception as e:
        logger.error(f"Error checking for existing study plan: {e}")
        return

    if not selected_subjects:
        logger.warning(f"No subjects selected for {plan_date_str}, cannot create study plan.")
        return

    try:
        study_plan_schema = notion_manager.retrieve_database(study_plan_db_id)
        todo_schema = notion_manager.retrieve_database(todo_db_id)
    except Exception as e:
        logger.error(f"Failed to retrieve database schemas: {e}")
        return

    plan_title = f"每日学习计划 - {plan_date_str}"
    study_plan_page_id = None

    # --- 1. 创建 学习计划 条目 ---
    try:
        study_plan_props = {}
        # '关键词' (Title)
        title_schema = study_plan_schema.get("properties", {}).get("关键词", {})
        study_plan_props["关键词"] = {"title": format_property_for_create(title_schema, plan_title)}

        # 'Date' (Date)
        date_schema = study_plan_schema.get("properties", {}).get("Date", {})
        study_plan_props["Date"] = {"date": format_property_for_create(date_schema, plan_date_str)}

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
                todo_props["预计完成时间"] = {"date": format_property_for_create(due_date_schema, plan_date_str)}

                # '时间段安排' (Date Range)
                date_range_schema = todo_schema.get("properties", {}).get("时间段安排", {})
                # For a single day, start and end are the same.
                date_range_value = {"start": plan_date_str, "end": None}
                todo_props["时间段安排"] = {"date": date_range_value}

                # '优先级' (Priority)
                priority_schema = todo_schema.get("properties", {}).get("优先级", {})
                todo_props["优先级"] = {"select": format_property_for_create(priority_schema, "mid")} # Default to 'mid'

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

    logger.info(f"Finished creating plan for {plan_date_str}. Created {todo_count} Todo items.")


def generate_period_plan(days_to_plan: int):
    """
    为未来 N 天生成学习计划。
    """
    logger.info(f"Generating study plan for the next {days_to_plan} days...")
    notion_manager = NotionManager()

    # Load DB IDs
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    ids_file_path = os.path.join(project_root, "data", "database_ids.json")
    try:
        with open(ids_file_path, 'r', encoding='utf-8') as f:
            db_ids = json.load(f)
        QUIZ_DB_ID = db_ids["Quiz库"]
        STUDY_PLAN_DB_ID = db_ids["学习计划"]
        TODO_DB_ID = db_ids["Todo库"]
    except Exception as e:
        logger.error(f"Failed to load database IDs: {e}")
        return

    # 1. quizzes pool
    upcoming_quizzes_pool = get_upcoming_quizzes(notion_manager, QUIZ_DB_ID, days_ahead=days_to_plan + 7)
    if not upcoming_quizzes_pool:
        logger.info("No upcoming quizzes found in the planning period. Exiting.")
        return
    
    # 按日期对池进行排序，以优先处理更紧急的任务
    upcoming_quizzes_pool.sort(key=lambda q: parse_page_property_value(q["properties"].get("下次回顾时间", {})) or "9999-12-31")


    # 2. 对每一天进行计划
    today = datetime.utcnow().date()
    for i in range(days_to_plan):
        current_plan_date = today + timedelta(days=i)
        logger.info(f"--- Planning for date: {current_plan_date.isoformat()} ---")

        if not upcoming_quizzes_pool:
            logger.warning(f"No more quizzes in the pool to plan for {current_plan_date.isoformat()}.")
            break

        # 3. 为目前日期选择quiz
        selected_subjects, selected_chapters, selected_ids = select_daily_quizzes(upcoming_quizzes_pool)
        
        if not selected_subjects:
            logger.info(f"No quizzes selected for {current_plan_date.isoformat()}. Moving to next day.")
            continue

        # 4. 对当前日期创建学习计划
        create_study_plan_and_todos(
            notion_manager,
            selected_subjects,
            selected_chapters,
            STUDY_PLAN_DB_ID,
            TODO_DB_ID,
            plan_date=current_plan_date
        )

        # 5. 将被分配的quiz池中取出
        upcoming_quizzes_pool = [
            quiz for quiz in upcoming_quizzes_pool if quiz["id"] not in selected_ids
        ]
        logger.info(f"{len(upcoming_quizzes_pool)} quizzes remaining in the pool.")

    logger.info(f"Finished planning for {days_to_plan} days.")
