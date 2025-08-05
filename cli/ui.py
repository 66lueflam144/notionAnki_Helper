from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import pyfiglet

def print_gradient_banner():
    console = Console()

    font = pyfiglet.Figlet(font='slant')
    ascii_art = font.renderText('Notion Anki Helper')

    text = Text(justify="center")
    colors = ["cyan", "magenta", "yellow"]
    lines = ascii_art.split("\n")
    
    for i, line in enumerate(lines):
        color = colors[i % len(colors)]
        text.append(line, style=f"bold {color}")
        if i < len(lines) - 1:
            text.append("\n")

    panel = Panel(
        text,
        border_style="bold green",
        title="[bold]Welcome[/bold]",
        title_align="center",
        padding=(1, 2)
    )
    
    console.print(panel)
    console.print("[bold green]Your personal automated study planner.[/bold green]", justify="center")
    console.print("[dim]Type 'help' for a list of commands or 'won' to exit.[/dim]", justify="center")
    console.print()
