from notion_client import Client
from config.settings import Settings
import logging

# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotionManager:
    def __init__(self):
        api_key = Settings.NOTION_API_KEY
        self.client = Client(auth=api_key)

    def list_databases(self):
        try:
            search_response = self.client.search(
                **{
                    "filter": {"property": "object", "value": "database"},
                    "sort": {"direction": "ascending", "timestamp": "last_edited_time"}
                }
            )
            databases = search_response.get("results", [])
            logger.info(f"Found {len(databases)} databases.")
            return databases
        except Exception as e:
            logger.error(f"Error listing databases: {e}")
            raise

    def retrieve_database(self, database_id: str):
        """
        获取指定数据库的完整元数据
        :param database_id:
        :return: filtered_info 字典
        """
        try:
            db_info = self.client.databases.retrieve(database_id=database_id)
            filtered_info = {
                "id": db_info.get("id"),
                "created_time": db_info.get("created_time"),
                "title": db_info.get("title"),
                "description": db_info.get("description"),
                "properties": db_info.get("properties", {}),
                # "key": db_info.get("key"),
                # "value": db_info.get("value")
            }

            logger.info(f"Retrieved info for database {database_id}.")
            return filtered_info
        except Exception as e:
            logger.error(f"Error retrieving database info for {database_id}: {e}")
            raise

    def create_page(self, database_id: str, properties_data: dict, children_data: list = None):
        try:
            parent =  {"database_id": database_id}
            page_data = {
                "parent": parent,
                "properties": properties_data
            }

            if children_data is not None:
                page_data["children"] = children_data

            new_page = self.client.pages.create(**page_data)
            page_id = new_page["id"]
            logger.info(f"Created new page with ID: {page_id} in database {database_id}")
            return new_page
        except Exception as e:
            logger.error(f"Error creating page in database {database_id}: {e}")
            raise

    def archive_page(self, page_id: str):
        try:
            updated_page = self.client.pages.update(page_id=page_id, archived=True)
            logger.info(f"Archived page with ID: {page_id}")
            return updated_page
        except Exception as e:
            logger.error(f"Error archiving page {page_id}: {e}")
            raise

    def get_page(self, page_id: str):
        try:
            page = self.client.pages.retrieve(page_id=page_id)
            blocks_response = self.client.blocks.children.list(block_id=page_id)
            blocks = blocks_response.get("results", [])
            logger.info(f"Retrieved page and blocks for ID: {page_id}")
            return {"page": page, "blocks": blocks}
        except Exception as e:
            logger.error(f"Error retrieving page {page_id}: {e}")
            raise

    def update_page_properties(self, page_id: str, properties_data: dict):
        try:
            updated_page = self.client.pages.update(page_id=page_id, properties=properties_data)
            logger.info(f"Updated properties for page ID: {page_id}.")
            return updated_page
        except Exception as e:
            logger.error(f"Error updating properties for page {page_id}: {e}")
            raise

    def query_database(self, database_id: str, filter_: dict=None, sorts: list = None, page_size: int = 100):
        try:
            has_more = True
            next_cursor = None

            while has_more:
                query_data = {
                    "database_id": database_id,
                    "page_size": page_size
                }
                if filter_:
                    query_data["filter"] = filter_
                if sorts:
                    query_data["sorts"] = sorts
                if next_cursor:
                    query_data["start_cursor"] = next_cursor

                response = self.client.databases.query(**query_data)
                pages = response.get("results", [])
                for page in pages:
                    yield page  # 使用生成器，内存友好

                next_cursor = response.get("next_cursor")
                has_more = response.get("has_more", False)

            logger.info(f"Finished querying database {database_id}.")
        except Exception as e:
            logger.error(f"Error querying database {database_id}: {e}")
            raise

    def get_all_pages_from_database(self, database_id: str, filter_: dict=None, sorts: list=None) -> list:
        pages = []
        try:
            for page in self.query_database(database_id, filter_, sorts):
                pages.append(page)
            return pages
        except Exception as e:
            logger.error(f"Error getting all pages from database {database_id}: {e}")
            raise