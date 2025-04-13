# Todoist CLI Tool

## Overview
This script is a command-line tool for managing tasks using the [Todoist API](https://developer.todoist.com/).  
It allows users to add tasks, list tasks in the first section of a project, and mark tasks as complete.  
It also includes an **interactive shell mode**, making it easier to manage your Todoist without typing full commands each time.

## Features
- Add tasks to Todoist
- List tasks in the first section of a project
- Complete tasks by number or name
- Automatically updates the repository once per day
- **Interactive Shell Mode**: Simply run `todo` to enter a prompt where you can manage tasks more naturally

## Requirements
- Python 3.x
- [Todoist API Token](https://developer.todoist.com/appconsole)
- A `.env` file with:
  ```
  TODOIST_TOKEN=your_todoist_api_token
  INBOX_ID=your_inbox_project_id
  ```

## Installation

### 1. Clone the repository:
```sh
git clone https://github.com/kentyja12/todoist-CLI.git
cd todoist-CLI
```

### 2. Install dependencies:
```sh
pip install -r requirements.txt
```

### 3. Create a `.env` file with the required credentials:
```
TODOIST_TOKEN=your_todoist_api_token
INBOX_ID=your_inbox_project_id
```

---

## Windows Users (PowerShell / CMD)

To use `todo` as a global command:

1. Edit the included `todo_sample.bat`:

   ```
   @echo off
   C:\Users\<YourUserName>\Documents\.env\Scripts\python.exe C:\Users\<YourUserName>\Documents\todoist-CLI\todoist-cli.py %*
   ```

   Replace `<YourUserName>` and paths with your actual environment.

2. Rename it to `todo.bat`.

3. Move (or copy) `todo.bat` to a folder like:
   ```
   C:\Users\<YourUserName>\Scripts\
   ```

4. Add that folder to your system's `PATH` so you can use `todo` from any terminal.

### Add to PATH

#### Option A: GUI (Recommended)
- Open **System Properties** → **Environment Variables**
- Under **User variables**, find and edit `Path`
- Add a new entry with the folder path (`C:\Users\<YourUserName>\Scripts`)
- Restart your terminal

#### Option B: Command Line

##### PowerShell:
```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Users\<YourUserName>\Scripts", "User")
```

##### CMD:
```cmd
setx Path "%Path%;C:\Users\<YourUserName>\Scripts"
```

🌀 Restart PowerShell or CMD to apply the change.

---

## macOS / Linux Users (bash / zsh / fish)

To use `todo` as a global command:

1. Create a symbolic link in a directory that's in your `PATH`. For example:
```sh
chmod +x todoist-cli.py  # Make sure it's executable

ln -s $(pwd)/todoist-cli.py ~/bin/todo  # or /usr/local/bin if you prefer
```

> Make sure `~/bin` or wherever you symlinked is in your `$PATH`.  
> You can check with:  
> ```sh
> echo $PATH
> ```

2. Or you can create a simple shell wrapper script like `todo`:

```sh
#!/bin/bash
python3 /full/path/to/todoist-cli.py "$@"
```

Place this in a folder like `/usr/local/bin` or `~/bin`, and make it executable:
```sh
chmod +x ~/bin/todo
```

---

## Test It Out

Try the following commands from any terminal:

```sh
todo add "Read book"
todo ls
todo check 1
```

Or enter **interactive shell mode** with:
```sh
todo
```

## Usage

### 1. Interactive Shell Mode
You can simply run `todo` with no arguments to enter an interactive shell.  
From there, you can use commands like `add`, `ls`, or `check` without retyping `todo`.

```sh
todo
```

Example session:
```
Todoist Interactive Mode Started (type 'exit' to quit)
todo> add Buy milk
todo> ls
todo> check 1
todo> exit
```

### 2. Add a Task
```sh
todo add "Buy groceries"
# or using alias
todo a "Buy groceries"

# Add multiple tasks
todo add "Buy groceries" "Clean my room" "Destroying evidence..."
```

### 3. List Tasks in the First Section
```sh
todo ls
```

### 4. Complete a Task by Number or Name
```sh
todo check 1
# or using alias
todo c 1
```

## License
This project is licensed under the MIT License.
---

## 🛠 One-liner Setup Tips for Windows (Current Directory)

If you want to install and use the `todo` command right in your current directory with a single PowerShell command, here's a ready-to-go example:

```powershell
git clone https://github.com/kentyja12/todoist-CLI.git .\todoist-CLI; cd .\todoist-CLI; python -m venv env; .\env\Scripts\Activate.ps1; pip install -r requirements.txt; echo "TODOIST_TOKEN=your_todoist_api_token`nINBOX_ID=your_inbox_project_id" > .env; echo "@echo off`r`n%CD%\env\Scripts\python.exe %CD%\todoist-cli.py %*" > todo.bat; $env:Path += ";$PWD"; .\todo.bat
```

> ⚠️ Replace `your_todoist_api_token` and `your_inbox_project_id` with your actual values.  
> This setup makes the `todo` command available for the current PowerShell session.

