import json
import os
import re
from collections import defaultdict
import logging

# logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def extract_model_from_pages_json(pages_data: list) -> dict:
    """
    从页面数据列表中提取模型。
    :param pages_data: 从 JSON 文件加载的页面数据列表。
    :return: 一个字典，键是属性名，值是属性类型。
             如果发现类型冲突，值可能是 'conflict' 或记录详细信息。
    """
    model = {}
    # 用于记录每个属性名出现过的所有类型，以便检测冲突
    prop_types_seen = defaultdict(set)

    logger.info(f"Analyzing {len(pages_data)} pages to extract model...")

    for page in pages_data:
        page_id = page.get("id")
        properties = page.get("properties", {})
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type")

            if prop_type is None:
                logger.warning(f"Page {page_id}: Property '{prop_name}' has no 'type' in parsed data.")
                continue

            # 记录该属性名见过的类型
            prop_types_seen[prop_name].add(prop_type)

            # 如果是第一次遇到这个属性名，直接记录
            if prop_name not in model:
                model[prop_name] = prop_type
            else:
                # 检查类型是否一致
                existing_type = model[prop_name]
                if existing_type != prop_type:
                    logger.warning(
                        f"Type conflict for property '{prop_name}': "
                        f"Found '{prop_type}' (in page {page_id}), "
                        f"previously recorded '{existing_type}'. "
                        f"All seen types: {sorted(prop_types_seen[prop_name])}"
                    )
                    # 可以选择标记为冲突，或保留第一个遇到的类型，或保留最后一个
                    # 这里我们选择标记为 'conflict'
                    model[prop_name] = 'conflict'

    logger.info("Model extraction complete.")
    return model

def load_pages_data(json_file_path: str) -> list:
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.error(f"Expected a list of pages in {json_file_path}, but got {type(data)}.")
            return []
        logger.info(f"Loaded {len(data)} pages from {json_file_path}")
        return data
    except FileNotFoundError:
        logger.error(f"File not found: {json_file_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {json_file_path}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading {json_file_path}: {e}")
    return []


def save_model(model: dict, output_file_path: str):
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(model, f, indent=2, ensure_ascii=False)
        logger.info(f"Model saved to {output_file_path}")
    except Exception as e:
        logger.error(f"Error saving model to {output_file_path}: {e}")


def find_page_data_files(data_dir: str) -> list:
    matching_files = []
    if not os.path.isdir(data_dir):
        logger.error(f"Data directory does not exist: {data_dir}")
        return matching_files

        # 列出目录下所有文件
    try:
        for filename in os.listdir(data_dir):
            # 检查是否是 .json 文件
            if filename.endswith('.json'):
                if '_' in filename and '_MODEL' not in filename and '_SCHEMA' not in filename:
                    full_path = os.path.join(data_dir, filename)
                    if os.path.isfile(full_path):  # 确保是文件
                        matching_files.append(full_path)
    except Exception as e:
        logger.error(f"Error listing files in {data_dir}: {e}")

    logger.info(f"Found {len(matching_files)} potential page data files in {data_dir}.")
    return matching_files


def main():
    """主函数：遍历 data 目录，处理所有匹配的 JSON 文件并生成模型。"""
    # --- 配置 ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, "data")

    logger.info(f"Searching for page data files in: {data_dir}")

    # 查找所有需要处理的页面数据文件
    page_data_files = find_page_data_files(data_dir)

    if not page_data_files:
        logger.info("No matching page data files found. Exiting.")
        return

    processed_count = 0
    for input_file_path in page_data_files:
        logger.info(f"\n--- Processing file: {os.path.basename(input_file_path)} ---")

        pages_data = load_pages_data(input_file_path)
        if not pages_data:
            logger.warning(f"Skipping {input_file_path} due to loading error or empty data.")
            continue

        model = extract_model_from_pages_json(pages_data)

        if model:
            # --- 构造输出模型文件名 ---
            # input_file_path 例如: .../data/学习计划_a1b2c3d4.json
            # input_filename 例如: 学习计划_a1b2c3d4.json
            input_filename = os.path.basename(input_file_path)
            # base_name 例如: 学习计划_a1b2c3d4
            base_name, _ = os.path.splitext(input_filename)
            # output_filename 例如: 学习计划_a1b2c3d4_MODEL.json
            output_filename = f"{base_name}_MODEL.json"

            # --- 构造结束 ---
            project_root_dir = os.path.dirname(data_dir)
            model_dir = os.path.join(project_root_dir, "model")
            os.makedirs(model_dir, exist_ok=True)
            output_file_path = os.path.join(model_dir, output_filename)
            save_model(model, output_file_path)

            # print(f"\nExtracted Model for {base_name}:")
            # print(json.dumps(model, indent=2, ensure_ascii=False))
            processed_count += 1
        else:
            logger.warning(f"No model could be extracted from {input_file_path}.")

    logger.info(f"\n--- Processing Complete ---")
    logger.info(f"Successfully processed {processed_count} out of {len(page_data_files)} files.")


if __name__ == "__main__":
    main()