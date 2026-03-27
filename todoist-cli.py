#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("TODOIST_TOKEN"):
    print("Error: TODOIST_TOKEN が .env に設定されていません。")
    exit(1)

if __name__ == "__main__":
    from todoist_tui import run_tui
    run_tui()
