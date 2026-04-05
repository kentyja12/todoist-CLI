# TOdash (Todoist TUI Tool)

<img width="811" height="328" alt="image" src="https://github.com/user-attachments/assets/9b94a1e5-05df-44b0-9252-98e5d7a4db27" />

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

### 2. Install with pipx

[pipx](https://pipx.pypa.io) installs the `todo` command globally without requiring you to manage a virtual environment.

```sh
# Install pipx (first time only)
pip install pipx
pipx ensurepath   # restart your terminal after this

# Install todash
pipx install .
```

To update later:

```sh
pipx reinstall todash
```

### 3. First-run setup

Run `todo` for the first time and the setup wizard will prompt you for your API token.
The config is saved to the OS-appropriate location automatically:

- **Windows**: `%APPDATA%\todash\.env`
- **macOS / Linux**: `~/.config/todash/.env`

You can edit this file later to change your token or the auto-refresh interval (`TTY`).

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
