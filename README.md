# Todoist CLI Tool

## Overview
This script is a command-line tool for managing tasks using the [Todoist API](https://developer.todoist.com/). It allows users to add tasks, list tasks in the first section of a project, and mark tasks as complete. Additionally, it ensures the repository is updated before execution.

## Features
- Add tasks to Todoist
- List tasks in the first section of a project
- Complete tasks by ID or name
- Automatically updates the repository once per day

## Requirements
- Python 3.x
- [Todoist API Token](https://developer.todoist.com/appconsole)
- A `.env` file with:
  ```
  TODOIST_TOKEN=your_todoist_api_token
  INBOX_ID=your_inbox_project_id
  ```

## Installation
1. Clone the repository:
   ```sh
   git clone https://github.com/your-repo/todoist-cli.git
   cd todoist-cli
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Create a `.env` file with the required credentials.

## Usage
### Add a Task
```sh
python todoist_cli.py add "Buy groceries"
```

### List Tasks in the First Section
```sh
python todoist_cli.py ls
```

### Complete a Task by Number or Name
```sh
python todoist_cli.py check 1
```

## License
This project is licensed under the MIT License.

