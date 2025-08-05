# core/data_parser.py
"""
模块用于将 Notion API 返回的复杂页面属性值对象解析为简单的 Python 数据类型。
遵循 Notion API 关于页面属性值的文档:
https://developers.notion.com/reference/page-property-values
"""

import logging
from typing import Any, Dict, Union, List, Optional

logger = logging.getLogger(__name__)

# 定义解析后可能的返回类型
ParsedValue = Union[str, int, float, bool, List[str], Dict[str, Any], None]

def parse_page_property_value(property_value_obj: Dict[str, Any]) -> ParsedValue:
    """
    解析单个 Notion 页面属性值对象。

    :param property_value_obj: Notion API 返回的属性值对象，
                               例如 {"title": [...]} 或 {"number": 123}。
    :return: 解析后的简单 Python 值。
    """
    if not isinstance(property_value_obj, dict):
        logger.warning(f"Expected dict for property value, got {type(property_value_obj)}. Returning as is.")
        return property_value_obj

    prop_type = property_value_obj.get("type")
    type_specific_value = property_value_obj.get(prop_type)

    if prop_type is None:
        logger.warning(f"Property value object missing 'type' key: {property_value_obj}. Returning raw object.")
        return property_value_obj

    try:
        # --- 处理各种属性类型 ---
        if prop_type in ["title", "rich_text"]:
            # 通常是包含文本对象的数组
            if isinstance(type_specific_value, list):
                # 提取 plain_text 并连接
                return "".join([item.get("plain_text", "") for item in type_specific_value])
            else:
                logger.warning(f"Unexpected value for {prop_type}: {type_specific_value}. Expected list.")
                return str(type_specific_value) if type_specific_value is not None else ""

        elif prop_type == "number":
            # 直接是数字或 None
            return type_specific_value # float, int, or None

        elif prop_type == "checkbox":
            # 直接是布尔值
            return type_specific_value # bool

        elif prop_type in ["created_time", "last_edited_time"]:
            # 直接是 ISO 8601 字符串
            return type_specific_value # str or None

        elif prop_type in ["created_by", "last_edited_by", "people"]:
            # 通常是用户对象数组
            if isinstance(type_specific_value, list):
                # 提取用户名称
                return [user.get("name", "Unknown User") for user in type_specific_value]
            elif isinstance(type_specific_value, dict):
                 # 单个用户对象 (不太常见，但 API 文档有时这样描述)
                 return [type_specific_value.get("name", "Unknown User")]
            else:
                logger.warning(f"Unexpected value for {prop_type}: {type_specific_value}. Expected list or dict.")
                return []

        elif prop_type == "select":
            # 通常是包含选项名称的字典，或 None
            if isinstance(type_specific_value, dict):
                return type_specific_value.get("name")
            elif type_specific_value is None:
                return None
            else:
                logger.warning(f"Unexpected value for select: {type_specific_value}. Expected dict or None.")
                return str(type_specific_value)

        elif prop_type == "status":
             # 与 select 类似
             if isinstance(type_specific_value, dict):
                 return type_specific_value.get("name")
             elif type_specific_value is None:
                 return None
             else:
                 logger.warning(f"Unexpected value for status: {type_specific_value}. Expected dict or None.")
                 return str(type_specific_value)

        elif prop_type == "multi_select":
            # 通常是包含选项字典的数组
            if isinstance(type_specific_value, list):
                return [option.get("name") for option in type_specific_value]
            else:
                logger.warning(f"Unexpected value for multi_select: {type_specific_value}. Expected list.")
                return []

        elif prop_type == "date":
            # 通常是包含 start, end, time_zone 的字典，或 None
            if isinstance(type_specific_value, dict):
                # 可以选择只返回 start，或者返回一个格式化的字符串
                start = type_specific_value.get("start")
                end = type_specific_value.get("end")
                # 简单处理：返回 start
                # 更复杂：可以格式化为 "start - end"
                return start # str or None
            elif type_specific_value is None:
                return None
            else:
                logger.warning(f"Unexpected value for date: {type_specific_value}. Expected dict or None.")
                return str(type_specific_value)

        elif prop_type == "url":
            # 直接是字符串或 None
            return type_specific_value # str or None

        elif prop_type == "email":
            # 直接是字符串或 None
            return type_specific_value # str or None

        elif prop_type == "phone_number":
             # 直接是字符串或 None
             return type_specific_value # str or None

        elif prop_type == "files":
            # 通常是文件对象数组
            if isinstance(type_specific_value, list):
                # 可以返回文件名列表或 URL 列表
                return [file_obj.get("name", "") for file_obj in type_specific_value]
            else:
                logger.warning(f"Unexpected value for files: {type_specific_value}. Expected list.")
                return []

        elif prop_type == "formula":
             # 结果取决于公式类型，可能是 number, string, boolean, date 等
             # type_specific_value 本身就是一个属性值对象，需要递归解析
             # 例如: {"type": "string", "string": "Result"}
             # 为了简化，我们直接返回其 type_specific_value (可能需要进一步处理)
             logger.info(f"Formula property encountered. Returning raw formula result: {type_specific_value}")
             return type_specific_value # 可能需要更复杂的处理

        elif prop_type == "relation":
             # 通常是包含相关页面 ID 的对象数组
             if isinstance(type_specific_value, list):
                 return [rel_obj.get("id") for rel_obj in type_specific_value]
             else:
                 logger.warning(f"Unexpected value for relation: {type_specific_value}. Expected list.")
                 return []

        elif prop_type == "rollup":
             # 结果取决于 rollup 配置，可能是 array, number, date, string 等
             # type_specific_value 通常包含 "type" 和具体的值 (如 "array", "number")
             rollup_type = type_specific_value.get("type") if isinstance(type_specific_value, dict) else None
             rollup_value = type_specific_value.get(rollup_type) if isinstance(type_specific_value, dict) else None

             if rollup_type == "array":
                 # 数组中的每个元素本身是一个属性值对象，需要解析
                 if isinstance(rollup_value, list):
                     parsed_array = []
                     for item in rollup_value:
                         # 递归调用解析每个数组元素
                         parsed_item = parse_page_property_value(item)
                         parsed_array.append(parsed_item)
                     return parsed_array
                 else:
                     logger.warning(f"Unexpected rollup array value: {rollup_value}. Expected list.")
                     return []
             elif rollup_type in ["number", "date", "string", "boolean"]:
                 # 直接返回值
                 return rollup_value
             elif rollup_type is None and rollup_value is None:
                  # 空的 rollup
                  return None
             else:
                 logger.info(f"Encountered rollup type '{rollup_type}' with value: {rollup_value}. Returning as is.")
                 return rollup_value # 返回原始值

        # --- 处理只读/未完全支持的类型 ---
        elif prop_type in ["unique_id"]: # Notion API 有时会返回这个
             return str(type_specific_value) if type_specific_value is not None else None

        else:
            # 对于未知或未处理的类型，记录日志并返回原始值
            logger.info(f"Parsing for property type '{prop_type}' is not implemented or unknown. Returning raw value.")
            return type_specific_value

    except Exception as e:
        logger.error(f"Error parsing property value object {property_value_obj}: {e}")
        # 返回原始对象或 None 以防万一
        return type_specific_value
