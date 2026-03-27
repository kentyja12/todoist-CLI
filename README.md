# Todoist CLI Tool

<img width="712" height="507" alt="image" src="https://github.com/user-attachments/assets/e6b5a45d-3661-4ccd-9421-aa6cc507b1fd" />

## Overview

This tool lets you manage Todoist from your terminal using a TUI (Terminal User Interface).
It displays your projects, sections, and tasks in a tree view so you can handle everything with just the keyboard.

## Features

- Tree view of projects, sections, and tasks (lazy loading)
- Add tasks with a name and description
- Complete, view, and edit tasks
- Undo / Redo support for add, complete, and edit operations
- Collapse all sections except the current one
- Vim-like line number jump
- Auto-update check on startup (interval set by `TTY` in `.env`)

## Requirements

- Python 3.10 or higher
- [Todoist API token](https://developer.todoist.com/appconsole)

## Installation

### 1. Clone the repository

```sh
git clone https://github.com/kentyja12/todoist-CLI.git
cd todoist-CLI
```

### 2. Create a virtual environment and install dependencies

```sh
python -m venv .env
# Windows
.env\Scripts\activate
# macOS / Linux
source .env/bin/activate

pip install -r requirements.txt
```

### 3. Create a `.env` file

```
TODOIST_TOKEN=your_todoist_api_token
TTY=300
```

- `TODOIST_TOKEN`: Your Todoist API token (required)
- `TTY`: Auto-update interval in seconds. Defaults to 3600 if not set

---

## Registering the `todo` Command

### Windows (PowerShell)

Create a `todo.bat` file and place it in a folder that is in your PATH.

```bat
@echo off
C:\path\to\.env\Scripts\python.exe C:\path\to\todoist-CLI\todoist-cli.py %*
```

### macOS / Linux

```sh
#!/bin/bash
/path/to/.env/bin/python /path/to/todoist-CLI/todoist-cli.py "$@"
```

Place this file at `~/bin/todo` or a similar location, then run `chmod +x` to make it executable.

---

## Key Bindings

| Key | Label | Description |
|---|---|---|
| `a` | Add Task | Add a new task |
| `Space` | Complete | Mark the selected task as complete |
| `Enter` | — | View and edit task details |
| `u` | Undo | Undo the last operation |
| `Ctrl+r` | Redo | Redo the last undone operation |
| `Ctrl+w` | Collapse Others | Collapse all sections except the current one |
| `g` | Jump | Enter line number jump mode |
| `r` | Refresh | Refresh the current project |
| `q` | Quit | Quit the app |

### Line Number Jump (`g`)

1. Press `g` to show a number next to every visible node
2. Type the number you want to jump to and press `Enter`
3. Press `Esc` to cancel

## License

MIT License
