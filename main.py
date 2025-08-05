import argparse
import logging
import sys

from config.settings import setup_logging
from scripts.generate_daily_plan import main as run_daily_plan
from scripts.anki_scheduler import update_quiz_schedule

setup_logging()
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Notion Anki Helper CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    parser_plan = subparsers.add_parser("plan-daily", help="Generate the daily study plan and TODOs.")
    parser_plan.set_defaults(func=lambda args: run_daily_plan())

    parser_update = subparsers.add_parser("update-quiz", help="Update a quiz's next review date based on a review log.")
    parser_update.add_argument("page_id", type=str, help="The page ID of the Quiz a review log entry.")
    parser_update.set_defaults(func=lambda args: update_quiz_schedule(args.page_id))

    args = parser.parse_args()

    logger.info(f"Executing command: {args.command}")
    try:
        args.func(args)
        logger.info(f"Command '{args.command}' executed successfully.")
    except Exception as e:
        logger.error(f"An error occurred during command '{args.command}': {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
