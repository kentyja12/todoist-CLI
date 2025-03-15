# Todoist CLI Tool

## Overview
This script is a command-line tool for managing tasks using the [Todoist API](https://developer.todoist.com/). It allows users to add tasks, list tasks in the first section of a project, and mark tasks as complete. Additionally, it ensures the repository is updated before execution.

## Features
- Add tasks to Todoist
- List tasks in the first section of a project
- Complete tasks by ID
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
   git clone https://github.com/kentyja12/todoist-CLI.git
   cd todoist-CLI
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Create a `.env` file with the required credentials.

## Usage
### Add a Task
```sh
todo add "Buy groceries"
## or
todo a "Buy groceries"
# Multiple tasks registered
todo add "Buy groceries" "clean my room" "destroying evidence..."
## or 
todo a "Buy groceries" "clean my room" "destroying evidence..."
```

### List Tasks in the First Section
```sh
todo ls
```

### Complete a Task by Number or Name
```sh
todo check 1
# or
todo c 1
```

## License
This project is licensed under the MIT License.

