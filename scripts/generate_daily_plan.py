import json
import logging
import os
import sys

from core.notion_client_wrapper import NotionManager
from core.daily_planner import (
    get_upcoming_quizzes,
    select_daily_quizzes,
    create_study_plan_and_todos,
)

logger = logging.getLogger(__name__)


def load_database_ids():
    """从 data/database_ids.json 加载数据库 ID"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    ids_file_path = os.path.join(project_root, "data", "database_ids.json")

    try:
        with open(ids_file_path, 'r', encoding='utf-8') as f:
            db_ids = json.load(f)
        logger.info(f"[✓] Loaded database IDs from {ids_file_path}")
        return db_ids
    except Exception as e:
        logger.error(f"[x] Error loading database IDs from {ids_file_path}: {e}")
        return None


def main():
    """主函数：执行每日计划生成的完整流程"""
    logger.info("Starting daily plan generation process...")

    db_ids = load_database_ids()
    if not db_ids:
        logger.error("Failed to load database IDs. Exiting.")
        sys.exit(1)

    try:
        QUIZ_DB_ID = db_ids["Quiz库"]
        STUDY_PLAN_DB_ID = db_ids["学习计划"]
        TODO_DB_ID = db_ids["Todo库"]
    except KeyError as e:
        logger.error(f"Required database title not found in database_ids.json: {e}.")
        sys.exit(1)

    notion_manager = NotionManager()

    # 1. 获取即将到来的 Quiz
    upcoming_quizzes = get_upcoming_quizzes(notion_manager, QUIZ_DB_ID)
    if not upcoming_quizzes:
        logger.info("No upcoming quizzes found. Exiting.")
        return

    # 2. 选择每日科目和章节
    selected_subjects, selected_chapters = select_daily_quizzes(upcoming_quizzes)
    if not selected_subjects:
        logger.info("No subjects selected based on the rules. Exiting.")
        return

    # 4. 创建计划和任务
    create_study_plan_and_todos(
        notion_manager,
        selected_subjects,
        selected_chapters,
        STUDY_PLAN_DB_ID,
        TODO_DB_ID,
    )

    logger.info("Daily plan generation process completed.")
