from __future__ import annotations

import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from .config import config_dir, config_file, is_configured

console = Console()


def setup_wizard() -> None:
    console.print()
    console.print(Panel(
        Text("Welcome to Todash!", justify="center", style="bold cyan"),
        subtitle="Vim-like TUI for Todoist",
        border_style="cyan",
    ))
    console.print()
    console.print("To get started, you need a [bold]Todoist API token[/bold].")
    console.print(
        "Get yours at: [link]https://app.todoist.com/app/settings/integrations/developer[/link]"
    )
    console.print()

    while True:
        token = Prompt.ask("[cyan]Paste your API token[/cyan]").strip()
        if token:
            break
        console.print("[red]Token cannot be empty. Please try again.[/red]")

    tty_input = Prompt.ask(
        "[cyan]Auto-refresh interval in seconds[/cyan] (default: [green]3600[/green], 0 to disable)",
        default="3600",
    ).strip()
    tty = tty_input if tty_input.isdigit() else "3600"

    cf = config_file()
    cf.parent.mkdir(parents=True, exist_ok=True)
    cf.write_text(f"TODOIST_TOKEN={token}\nTTY={tty}\n", encoding="utf-8")

    console.print()
    console.print(f"[green]✓[/green] Config saved to: [dim]{cf}[/dim]")
    console.print("[green]✓[/green] Setup complete! Starting Todash...\n")


def main() -> None:
    if not is_configured():
        setup_wizard()

    load_dotenv(config_file())

    import os
    if not os.getenv("TODOIST_TOKEN"):
        console.print("[red]Error:[/red] TODOIST_TOKEN is not set.")
        console.print(f"Edit [dim]{config_file()}[/dim] and add your token, then run [bold]todo[/bold] again.")
        sys.exit(1)

    from .tui import run_tui
    run_tui()
