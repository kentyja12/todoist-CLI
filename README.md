# TOdash (Todoist TUI Tool)

<img width="633" height="482" alt="image" src="https://github.com/user-attachments/assets/c58ea4dd-8ce3-4ac8-8875-42df9aebc06c" />

## Overview

I renamed the project from Todoist-CLI to Todash.
This tool lets you manage Todoist from your terminal using a TUI (Terminal User Interface).
It displays your projects, sections, and tasks in a list view with line numbers on the far left, so you can handle everything with just the keyboard.

## Features

- List view of projects, sections, and tasks (lazy loading)
- Always-visible line numbers at the far left of every row
- Add tasks with a name and optional description
- Complete, view, and edit tasks
- Undo / Redo support for add, complete, and edit operations
- Collapse all sections except the current one (`Ctrl+w`)
- Vim-like mode system (Normal / Command / Colon / Move)
- Line number jump: `Esc → :<N>g → Enter`
- Task move mode: `Esc → :mv → Enter`
- Auto-update check on startup (interval set by `TTY` in `.env`)
- Optimistic UI — pending operations shown dimmed in real time

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

## Mode System

This tool uses a Vim-like modal input system.

```
Normal ──[Esc]──▶ Command ──[Esc]──▶ Normal
                     │
                    [:]──▶ Colon ──[Esc]──▶ Normal
                     │
                   [:mv]──▶ Move  ──[Esc]──▶ Normal
```

- **Normal**: navigate freely with `j` / `k` and `Enter`
- **Command**: single-key actions (`a`, `Space`, `r`, `e`, `:`)
- **Colon**: type a command and press `Enter` (e.g. `5g`, `mv`)
- **Move**: select a destination task with `Enter`

---

## Key Bindings

| Key | Mode | Action |
|---|---|---|
| `j` | All | Move cursor down |
| `k` | All | Move cursor up |
| `Enter` | Normal | Expand / collapse project or section |
| `q` | All | Quit |
| `Esc` | Normal | Enter Command mode |
| `Esc` | Command / Colon / Move | Return to Normal mode |
| `a` | Command | Add a task at the current location |
| `Space` | Command | Mark the selected task as complete |
| `e` | Command | Edit the selected task |
| `r` | Command | Refresh the current project |
| `:` | Command | Enter Colon command input |
| `:<N>g` + `Enter` | Colon | Jump to line N |
| `:mv` + `Enter` | Colon | Enter Move mode for the selected task |
| `Enter` | Move | Move the task to just below the destination |
| `u` | All | Undo the last operation |
| `Ctrl+r` | All | Redo the last undone operation |
| `Ctrl+w` | All | Collapse all sections except the current one |

### Line Number Jump

Line numbers are always displayed at the far left of each row.

1. Press `Esc` to enter Command mode
2. Press `:` to enter Colon mode
3. Type the line number followed by `g` (e.g. `5g`) and press `Enter`
4. Press `Esc` to cancel

### Task Move

1. Select the task you want to move
2. Press `Esc → : → mv → Enter` to enter Move mode (the task turns yellow)
3. Navigate to the destination task and press `Enter`
4. Press `Esc` to cancel

## License

MIT License
