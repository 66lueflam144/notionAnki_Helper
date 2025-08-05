import logging

# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _format_common_property_value(prop_type: str, user_input: str):
    """
    处理创建和更新时通用的属性值格式化。
    这些类型的创建和更新格式基本相同。
    """
    try:
        if prop_type == "title":
            return [{"text": {"content": user_input}}]
        elif prop_type == "rich_text":
            return [{"text": {"content": user_input}}]
        elif prop_type == "number":
            return float(user_input)
        elif prop_type == "checkbox":
            # 统一使用 'true' 进行判断
            return user_input.lower() in ['true', '1', 'yes', 'on']
        elif prop_type == "url":
            return user_input if user_input else None
        elif prop_type == "email":
            return user_input if user_input else None
        elif prop_type == "phone_number":
            return user_input if user_input else None
        elif prop_type == "date":
            # 基本日期格式化，假设用户输入是 ISO 字符串 (e.g., "2024-10-28" or "2024-10-28T10:00:00Z")
            formatted_date = {"start": user_input} if user_input else None
            logger.debug(f"[_format_common_property_value] Date input: '{user_input}', formatted: {formatted_date}")
            return formatted_date
        # 可以根据需要为其他通用类型添加处理...
    except ValueError as e:
        logger.error(f"Error converting input '{user_input}' for type '{prop_type}': {e}")
        # 对于数字转换错误等，可以选择返回 None 或默认值，或重新抛出异常
        # 这里选择返回 None，让调用者决定如何处理
        return None

def _validate_and_format_select_like(property_schema: dict, user_input: str, prop_type: str, is_update: bool):
    """
    验证并格式化 select, multi_select, status 类型的属性值。
    :param property_schema: 属性的 schema 对象。
    :param user_input: 用户提供的输入字符串。
    :param prop_type: 属性类型 ('select', 'multi_select', 'status')。
    :param is_update: 是否是更新操作（影响空值处理）。
    :return: 格式化后的值，或 None/[]（取决于类型和 is_update）。
    """
    # 确定 schema key 和 option key
    schema_key = prop_type
    options_key = "options"

    # 获取选项列表
    options = property_schema.get(schema_key, {}).get(options_key, [])
    option_names = [opt["name"] for opt in options]

    if prop_type == "select" or prop_type == "status":
        # Select/Status: 单个选项
        if not user_input:
            # 创建时通常跳过，更新时可以设为 None 来清除
            return None if is_update else None # 或者 return None # 创建时也返回 None
        if user_input in option_names:
            return {"name": user_input}
        else:
            logger.warning(
                f"Input '{user_input}' for {prop_type} property '{property_schema['name']}' "
                f"is not a valid option {option_names}. Setting to None."
            )
            return None

    elif prop_type == "multi_select":
        # Multi-Select: 多个选项 (逗号分隔)
        if not user_input:
             # 创建时跳过，更新时设为 [] 来清除
            return [] if is_update else [] # 或者 return [] # 创建时也返回 []

        input_options = [opt.strip() for opt in user_input.split(",") if opt.strip()]
        valid_options = [{"name": opt} for opt in input_options if opt in option_names]

        if len(valid_options) != len(input_options):
            invalid = set(input_options) - set(option_names)
            logger.warning(
                f"Some inputs {invalid} for multi_select property '{property_schema['name']}' "
                f"are not valid options {option_names}."
            )
        # 修复：无论是否有无效选项，都返回处理后的 valid_options 列表
        return valid_options

def format_property_for_create(property_schema: dict, user_input: str):
    """
    根据数据库属性 schema 和用户输入，格式化为创建页面所需的属性值。
    """
    prop_type = property_schema["type"]
    prop_name = property_schema["name"]

    # 处理通用类型
    common_value = _format_common_property_value(prop_type, user_input)
    if common_value is not None or prop_type in ["title", "rich_text", "number", "checkbox", "url", "email", "phone_number", "date"]:
        return common_value

    # 处理 Select-like 类型 (创建)
    if prop_type in ["select", "multi_select", "status"]:
        # API 限制：不能通过 API 修改 status 选项，但可以设置现有选项
        # 因此 status 的处理逻辑与 select/multi_select 类似（验证选项）
        return _validate_and_format_select_like(property_schema, user_input, prop_type, is_update=False)

    # 处理只读或特殊限制类型
    elif prop_type in ["created_time", "last_edited_time", "created_by", "last_edited_by", "formula", "rollup", "files"]:
        logger.info(f"Property '{prop_name}' of type '{prop_type}' cannot be set during page creation. Skipping.")
        return None

    # 处理需要特殊逻辑但未在此实现的类型
    elif prop_type == "relation":
        if not user_input:
            return []
        page_ids = [pid.strip() for pid in user_input.split(",") if pid.strip()]
        return [{"id": pid} for pid in page_ids]
    else:
        logger.info(f"Unknown or unhandled property type '{prop_type}' for property '{prop_name}' during creation. Returning raw input.")
        return user_input


def format_property_for_update(property_schema: dict, user_input: str):
    """
    根据数据库属性 schema 和用户输入，格式化为更新页面属性所需的属性值。
    """
    prop_type = property_schema["type"]
    prop_name = property_schema["name"]

    # 处理通用类型 (与创建时相同)
    common_value = _format_common_property_value(prop_type, user_input)
    if common_value is not None or prop_type in ["title", "rich_text", "number", "checkbox", "url", "email", "phone_number", "date"]:
        return common_value

    # 处理 Select-like 类型 (更新)
    if prop_type in ["select", "multi_select", "status"]:
         # API 限制：不能通过 API 修改 status 选项，但可以设置/清除现有选项
        return _validate_and_format_select_like(property_schema, user_input, prop_type, is_update=True)

    # 处理只读或特殊限制类型
    elif prop_type in ["created_time", "last_edited_time", "created_by", "last_edited_by", "formula", "rollup", "files"]:
        logger.info(f"Property '{prop_name}' of type '{prop_type}' cannot be updated. Skipping.")
        return None

    # 处理需要特殊逻辑但未在此实现的类型
    elif prop_type in ["relation", "people"]:
         logger.info(f"Formatting for property type '{prop_type}' is not implemented or requires special handling in 'update'. Skipping.")
         return None # 或 return user_input

    else:
        logger.info(f"Unknown or unhandled property type '{prop_type}' for property '{prop_name}' during update. Returning raw input.")
        return user_input
