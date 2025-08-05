import os
from dotenv import load_dotenv
import logging
import logging.config
import colorlog


def setup_logging():
    """配置全局日志，包括 colorlog"""
    # 定义日志格式
    # %(log_color)s 是 colorlog 特有的，用于根据日志级别着色
    log_format = "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 配置 colorlog 的 formatter
    formatter = colorlog.ColoredFormatter(
        log_format,
        datefmt="%Y-%m-%d %H:%M:%S",  # 自定义日期格式
        # 自定义颜色
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        }
    )

    # 创建控制台处理器 (StreamHandler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 获取 root logger (这是全局 logger)
    root_logger = logging.getLogger()
    # 设置 root logger 的级别
    root_logger.setLevel(logging.INFO)  # 或者从环境变量读取
    # 清除现有的 handlers (防止重复添加)
    root_logger.handlers.clear()
    # 添加我们配置好的 colorlog handler
    root_logger.addHandler(console_handler)


# 指定.env文件的绝对路径
config_dir = os.path.dirname(__file__)
# 获取项目根目录路径 (.../your_project) - config 的父目录
project_root_dir = os.path.dirname(config_dir)
# 指定 .env 文件的绝对路径 (相对于项目根目录)
env_path = os.path.join(project_root_dir, '.env')

load_dotenv(dotenv_path=env_path)


class Settings:
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    DATABASE_IDS = [db_id.strip() for db_id in os.getenv("DATABASE_IDS", "").split(",") if db_id.strip()]
    LOCAL_DATA_PATH = os.getenv("LOCAL_DATA_PATH", "./model")
    PAGE_ID = os.getenv("PAGE_ID")

    CURRENT_SUBJECTS = [
        "计算机网络", "计算机组成原理", "操作系统", "概率论与数理统计"
        # 未来可能添加的科目可以暂时注释掉或保留在这里，但不在 CURRENT_SUBJECTS 中使用
        # "英语写作", "数据挖掘", "物联网工程", "线性代数", "网络工程", "数据结构"
    ]

    # Todo库 - 任务类型选项
    TODO_TASK_TYPES = ["quiz编写", "复习", "学习", "写作练习", "作业"]

    # Quiz库 - 学习状态选项
    QUIZ_LEARNING_STATES = ["DONE", "PROGRESS", "TODO"]

    # Quiz库 - 难度选项
    QUIZ_DIFFICULTY_LEVELS = ["mid", "hard", "easy"]

    # Quiz库 - 所属课程选项 (通常与 CURRENT_SUBJECTS 有交集)
    QUIZ_COURSES = ["概率论与数理统计", "计算机网络", "计算机组成原理", "操作系统"]

    # Quiz库 - 章节/关键词 (这是一个动态列表，可能随课程增加)
    QUIZ_CHAPTERS = [
        "01-计算机网络体系结构", "02-物理层", "03-数据链路层",
        "05-中央处理器",
        "01-随机事件及其矣系与运算", "02-随机变量及其概率分布",
        "03-多维随机变量及其分布", "04-随机变量的数字特征",
        "05-大数定律与中心极限定理", "06-数理统计的基本概念", "07-参数估计",
        "03-内存管理", "05-I/O管理", "06-总线"
        # 可以继续添加其他章节
    ]

    def validate_api(self):
        """验证必要配置"""
        errors = []
        if not self.NOTION_API_KEY:
            errors.append("NOTION_API_KEY 未设置")
        return errors

    def validate_page(self):
        """验证页面ID配置"""
        errors = []
        if not self.PAGE_ID:
            errors.append("PAGE_ID 未设置")
        return errors

    def validate_databases(self):
        """验证数据库ID列表"""
        errors = []
        if not self.DATABASE_IDS:
            errors.append("DATABASE_IDS 未设置或为空")
        return errors


settings = Settings()
setup_logging()