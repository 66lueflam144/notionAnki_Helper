import json
import logging
import os
import sys
from datetime import datetime, timedelta

from core.data_parser import parse_page_property_value
from core.notion_client_wrapper import NotionManager
from utils.helper import format_property_for_update

# --- 配置 ---
# 从 database_ids.json 加载数据库 ID
def load_database_ids():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    ids_file_path = os.path.join(project_root, "data", "database_ids.json")
    try:
        with open(ids_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load database IDs from {ids_file_path}: {e}")
        raise

# --- Anki SM-2 算法简化实现 ---
# 参考: https://supermemo.guru/wiki/SM-2_algorithm
# 这里做了简化，假设起始难度因子(EF)为2.5，起始间隔为1天
# 并且直接使用回顾次数作为算法迭代次数的近似

def calculate_next_review_date_sm2(review_quality: int, review_count: int, ease_factor: float = 2.5) -> str:
    """
    简化版 Anki SM-2 算法计算下次回顾日期。
    :param review_quality: 回顾质量 (0-糟糕, 1-困难, 2-好, 3-简单)。
    :param review_count: 当前复习次数 (从 Quiz 页面的 Rollup 属性获取)。
    :param ease_factor: 当前难度因子 (简化处理，使用固定值)。
    :return: 下次回顾日期的 ISO 格式字符串 (YYYY-MM-DD)。
    """
    # --- 简化逻辑 ---
    # 1. 如果质量是 0 (失败)，重置间隔为 1 天。
    # 2. 否则，根据 EF 和复习次数计算新间隔。
    # 3. 更新 EF (简化，这里不实际更新 EF，只根据质量调整间隔倍数)。
    # 4. 计算下次日期。

    if review_quality < 0 or review_quality > 3:
        logging.warning(f"Invalid review_quality: {review_quality}. Clamping to 0-3.")
        review_quality = max(0, min(3, review_quality))

    interval_days = 1 # 起始间隔
    ef = ease_factor # 简化，不动态调整 EF

    if review_count > 0: # 不是第一次复习
        if review_quality == 0:
            interval_days = 1 # 失败则重学
        else:
            # 简化计算：间隔 = 上次间隔 * EF * (质量因子)
            # 这不是标准 SM-2，一个基于质量和次数的简单增长模型
            quality_multiplier = 1.0 + (review_quality - 1) * 0.2 # 1(好)=1.0, 2(困难)=0.8, 3(简单)=1.2
            interval_days = max(1, int(1 * ef * quality_multiplier * review_count)) # 用 review_count 作为迭代次数近似

    # 根据质量调整 EF (简化版)
    if review_quality < 2:
        ef = max(1.3, ef - 0.1)
    elif review_quality > 2:
        ef = ef + 0.1
    # review_quality == 2 时 EF 不变

    # 计算下次回顾日期
    next_review_date = datetime.utcnow().date() + timedelta(days=interval_days)
    logging.info(f"Anki Calculation - Quality: {review_quality}, Count: {review_count}, EF: {ef:.2f} -> Interval: {interval_days} days -> Date: {next_review_date.isoformat()}")
    return next_review_date.isoformat()

def update_quiz_schedule(review_log_page_id: str):
    """
    基于一条 Quiz回顾日志，更新其关联 Quiz 题目的下次回顾时间。
    :param review_log_page_id: 刚创建或更新的 Quiz回顾日志 页面 ID。
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.info(f"Starting ANKI update process for review log: {review_log_page_id}")

    # 1. 加载数据库 ID
    try:
        db_ids = load_database_ids()
        QUIZ_DB_ID = db_ids.get("Quiz库")
        if not QUIZ_DB_ID:
            logger.error("Quiz库 database ID not found in database_ids.json.")
            return
    except Exception as e:
        logger.error(f"Failed to load database IDs: {e}")
        return

    notion_manager = NotionManager()

    # 2. 获取回顾日志页面
    try:
        log_page_data = notion_manager.get_page(review_log_page_id)
        log_page_props = log_page_data["page"]["properties"]
        logger.debug(f"Fetched review log page properties: {list(log_page_props.keys())}")
    except Exception as e:
        logger.error(f"Error fetching review log page {review_log_page_id}: {e}")
        return

    # 3. 解析回顾日志关键属性
    # --- 获取回顾效果 ---
    review_effect_obj = log_page_props.get("回顾效果", {})
    review_effect = parse_page_property_value(review_effect_obj) # 应为字符串，如 "bad", "good"
    logger.debug(f"Parsed '回顾效果': {review_effect}")
    if not review_effect:
        logger.warning(f"Review log {review_log_page_id} has no '回顾效果'. Skipping update.")
        return

    # 将回顾效果映射到 Anki 质量评分 (0-2)
    effect_to_quality = {
        "bad": 0,
        "attention": 1,
        "good": 2
    }
    review_quality = effect_to_quality.get(review_effect.lower(), 2) # 默认 "good"
    logger.info(f"Mapped review effect '{review_effect}' to quality score: {review_quality}")

    # --- 获取关联的 Quiz 题目 ID ---
    related_quiz_obj = log_page_props.get("所属Quiz题目", {}) # Relation type
    related_quiz_ids = parse_page_property_value(related_quiz_obj) # 应为 [page_id, ...] 列表
    logger.debug(f"Parsed '所属Quiz题目' relation: {related_quiz_ids}")
    if not related_quiz_ids or not isinstance(related_quiz_ids, list) or len(related_quiz_ids) == 0:
        logger.warning(f"Review log {review_log_page_id} has no valid '所属Quiz题目' relation. Skipping update.")
        return

    quiz_page_id = related_quiz_ids[0] # 假设只关联一个题目
    logger.info(f"Found related Quiz page ID: {quiz_page_id}")

    # 4. 获取 Quiz 页面信息以用于 Anki 计算
    review_count = 1 # 默认值
    try:
        quiz_page_data = notion_manager.get_page(quiz_page_id)
        quiz_props = quiz_page_data["page"]["properties"]
        logger.debug(f"Fetched quiz page properties: {list(quiz_props.keys())}")

        # --- 获取回顾次数 (Rollup - Number) ---
        review_count_obj = quiz_props.get("回顾次数", {})
        parsed_review_count = parse_page_property_value(review_count_obj)
        logger.debug(f"Parsed '回顾次数' (Rollup): {parsed_review_count}")
        if isinstance(parsed_review_count, (int, float)):
            review_count = int(parsed_review_count)
        else:
            logger.info(f"'回顾次数' is not a number ({parsed_review_count}), using default value: {review_count}")
    except Exception as e:
        logger.warning(f"Could not fetch or parse Quiz page {quiz_page_id} for state, using defaults: {e}")

    # 5. 执行 Anki 算法
    try:
        new_next_review_date_str = calculate_next_review_date_sm2(
            review_quality=review_quality,
            review_count=review_count,
            ease_factor=2.5 # 简化，使用固定 EF
        )
        logger.info(f"Calculated new next review date: {new_next_review_date_str}")
    except Exception as e:
        logger.error(f"Error calculating next review date: {e}")
        return

    # 6. 获取 Quiz库 数据库 Schema 和 "下次回顾时间" 属性 Schema
    try:
        quiz_db_info = notion_manager.retrieve_database(QUIZ_DB_ID)
        quiz_properties_schema = quiz_db_info["properties"]
        next_review_date_schema = quiz_properties_schema.get("下次回顾时间")

        if not next_review_date_schema:
            logger.error("Schema for '下次回顾时间' property not found in Quiz database.")
            return
        logger.debug("Retrieved Quiz database schema and '下次回顾时间' property schema.")
    except Exception as e:
        logger.error(f"Error retrieving Quiz database schema: {e}")
        return

    # 7. 格式化新值
    try:
        formatted_new_date = format_property_for_update(next_review_date_schema, new_next_review_date_str)
        logger.debug(f"[Formatted] new date value for Notion API: {formatted_new_date}")
        logger.debug(
            f"DEBUG: new_next_review_date_str = '{new_next_review_date_str}' (type: {type(new_next_review_date_str)})")
        logger.debug(f"[DEBUG]: next_review_date_schema['type'] = '{next_review_date_schema.get('type')}'")
        logger.debug(f"[DEBUG]: next_review_date_schema['name'] = '{next_review_date_schema.get('name')}'")
        logger.debug(f"[DEBUG]: formatted_new_date = {formatted_new_date} (type: {type(formatted_new_date)})")

        if formatted_new_date is None:
             logger.error("Formatting new date returned None.")
             return
    except Exception as e:
        logger.error(f"Error formatting date '{new_next_review_date_str}': {e}")
        return

    # 8. 构造更新数据
    properties_to_update = {
        "下次回顾时间": formatted_new_date
    }
    logger.debug(f"DEBUG: properties_to_update = {properties_to_update}")
    logger.debug(f"Prepared properties update data: {properties_to_update}")

    # 9. 更新 Quiz 页面
    try:
        updated_page = notion_manager.update_page_properties(quiz_page_id, properties_to_update)
        logger.info(f"Successfully updated '下次回顾时间' for Quiz page {quiz_page_id} to {new_next_review_date_str}")
    except Exception as e:
        logger.error(f"Error updating Quiz page {quiz_page_id}: {e}")

def main():
    """主函数 - 可以通过命令行参数传入 review_log_page_id"""
    if len(sys.argv) != 2:
        print("Usage: python scripts/anki_scheduler.py <review_log_page_id>")
        sys.exit(1)

    review_log_page_id = sys.argv[1]
    update_quiz_schedule(review_log_page_id)

if __name__ == "__main__":
    main()