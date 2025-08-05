# scripts/fetch_and_parse_db.py
"""
示例脚本：列出可访问的数据库，让用户选择一个，
然后获取该数据库的所有页面并解析其属性。
"""

from core.notion_client_wrapper import NotionManager
from core.data_parser import parse_page_property_value
import json
import os

def main():
    nm = NotionManager()

    # 1. 列出数据库
    print("Fetching accessible databases...")
    try:
        databases = nm.list_databases()
    except Exception as e:
        print(f"Failed to list databases: {e}")
        return

    if not databases:
        print("No databases found.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, "data")
    os.makedirs(data_dir, exist_ok=True)

    database_info = {}

    print("\nAvailable Databases:")
    for i, db in enumerate(databases):
        db_id = db["id"]
        title_objs = db.get("title", [])
        db_title = "".join([t.get("plain_text", "") for t in title_objs]) if title_objs else "Untitled"
        database_info[db_title] = db_id
        print(f"  {i + 1}. ID: {db_id}")
        print(f"      Title: {db_title}")
        print("-" * 30)

    output_dbs_path = os.path.join(data_dir, "database_ids.json")
    try:
        with open(output_dbs_path, 'w', encoding='utf-8') as f:
            json.dump(database_info, f, indent=4, ensure_ascii=False)
        print(f"\nSuccessfully saved database IDs to: {output_dbs_path}")
    except IOError as e:
        print(f"\nError writing to file: {e}")

    # 2. 让用户选择数据库
    try:
        choice = int(input("Enter the number of the database to fetch: ")) - 1
        if 0 <= choice < len(databases):
            selected_db_id = databases[choice]["id"]
            print(f"\nSelected database ID: {selected_db_id}")
        else:
            print("Invalid choice.")
            return
    except ValueError:
        print("Invalid input. Please enter a number.")
        return



    # 3. 获取数据库 Schema (用于后续可能的属性信息)
    try:
        db_info = nm.retrieve_database(selected_db_id)
        db_title_rich = db_info.get("title", [])
        db_title = "".join([t.get("plain_text", "") for t in db_title_rich]) if db_title_rich else "Untitled"
        db_properties_schema = db_info.get("properties", {})
        print(f"\nFetching pages from database: {db_title} ({selected_db_id})")


    except Exception as e:
        print(f"Failed to retrieve database info: {e}")
        return

    # 4. 查询并解析页面
    print("\nFetching and parsing pages...")
    parsed_pages = []
    page_count = 0
    try:
        # 使用生成器逐个处理页面
        for page in nm.query_database(selected_db_id):
            page_id = page["id"]
            page_properties_raw = page.get("properties", {})

            # 解析每个属性
            parsed_properties = {}
            for prop_name, prop_value_obj in page_properties_raw.items():
                prop_type = prop_value_obj.get("type")
                parsed_value = parse_page_property_value(prop_value_obj)
                parsed_properties[prop_name] = {
                    "type": prop_type,
                    "value": parsed_value
                }

            parsed_pages.append({
                "id": page_id,
                "properties": parsed_properties
                # 可以根据需要添加其他页面元数据，如 created_time, url 等
            })
            page_count += 1
            if page_count % 50 == 0:  # 每50页打印一次进度
                print(f"  Processed {page_count} pages...")

        print(f"\nFinished processing {page_count} pages.")

        # 5. 输出结果 (例如，打印前几个或保存到文件)
        print(f"\n--- Parsed Data for first 2 pages ---")
        for i, parsed_page in enumerate(parsed_pages[:2]):
            print(f"\nPage {i + 1} (ID: {parsed_page['id']}):")
            # 以 JSON 格式美化输出
            # print(json.dumps(parsed_page['properties'], indent=2, ensure_ascii=False))

        import re
        safe_db_title = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', db_title)  # 用下划线替换不安全字符
        safe_db_title = safe_db_title[:50]  # 限制长度，防止文件名过长
        # 取数据库 ID 的前8位作为简短标识 (可选，根据需要调整位数)
        short_db_id = selected_db_id.replace('-', '')[:8]  # 移除连字符并取前8位


        # 组合标题和短ID作为前缀
        filename_prefix = f"{safe_db_title}_{short_db_id}"

        output_filename = os.path.join(data_dir, f"{filename_prefix}.json")
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(parsed_pages, f, indent=2, ensure_ascii=False)
        print(f"\nAll parsed data saved to {output_filename}")

    except Exception as e:
        print(f"An error occurred during fetching/parsing: {e}")
        import traceback
        traceback.print_exc()  # 打印详细错误堆栈


if __name__ == "__main__":
    main()