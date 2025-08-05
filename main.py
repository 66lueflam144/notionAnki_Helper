import argparse
import logging
import sys
import shlex

from rich.console import Console

from config.settings import setup_logging
from scripts.generate_daily_plan import main as run_daily_plan
from scripts.anki_scheduler import update_quiz_schedule, process_all_review_logs
from core.daily_planner import generate_period_plan
from cli.ui import print_gradient_banner

setup_logging()
logger = logging.getLogger(__name__)
console = Console()


def create_parser():
    parser = argparse.ArgumentParser(
        description="Notion Anki Helper CLI - Your personal automated study planner.",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- Custom Help Command ---
    subparsers.add_parser("help", help="Show this help message.")

    # --- Command: plan-daily ---
    subparsers.add_parser("plan-daily", help="Generate the daily study plan and TODOs for today.")

    # --- Command: update-quiz ---
    parser_update = subparsers.add_parser("update-quiz", help="Update a quiz's next review date based on a review log.")
    parser_update.add_argument("page_id", type=str, help="The page ID of the Quiz review log entry.")

    # --- Command: process-reviews ---
    subparsers.add_parser("process-reviews", help="Process all unprocessed review logs.")

    # --- Command: plan-period ---
    parser_period = subparsers.add_parser("plan-period", help="Generate study plans for a future period.")
    parser_period.add_argument("--days", type=int, default=3, help="Number of days to plan for (default: 3).")
    
    return parser


def main():
    parser = create_parser()
    print_gradient_banner()

    while True:
        try:
            input_str = console.input("[bold cyan]>>>[/bold cyan] ")
            if not input_str:
                continue

            command_args = shlex.split(input_str)
            command_name = command_args[0]

            if command_name.lower() == "won":
                console.print("[bold yellow]FINE![/bold yellow]")
                break
            
            if command_name.lower() == "help":
                parser.print_help()
                continue

            try:
                args = parser.parse_args(command_args)
            except SystemExit:
                continue

            logger.info(f"Executing command: [bold cyan]{args.command}[/bold cyan]")
            
            if args.command == "plan-daily":
                run_daily_plan()
            elif args.command == "update-quiz":
                update_quiz_schedule(args.page_id)
            elif args.command == "process-reviews":
                process_all_review_logs()
            elif args.command == "plan-period":
                generate_period_plan(args.days)
            
            logger.info(f"Command '[bold green]{args.command}[/bold green]' executed successfully.")

        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    main()
