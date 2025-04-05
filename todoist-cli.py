import argparse
import os
import subprocess
import datetime
import sys
from dotenv import load_dotenv
from todoist_api_python.api import TodoistAPI
from pathlib import Path

# Load .env file
load_dotenv()

# Create a global API instance
SCRIPT_PATH = Path(os.path.abspath(__file__))
REPO_PATH = SCRIPT_PATH.resolve().parent
TODOIST_TOKEN = os.getenv("TODOIST_TOKEN")
INBOX_ID = os.getenv("INBOX_ID")
LAST_UPDATE_FILE = ".last_update"
api = TodoistAPI(TODOIST_TOKEN)

if not TODOIST_TOKEN or not INBOX_ID:
    print("Error: TODOIST_TOKEN or INBOX_ID is not set in the .env file.")
    exit(1)

def check_and_update_repo():
    """Update the repository if it's the first execution of the day."""
    today = datetime.date.today().isoformat()
    if os.path.exists(LAST_UPDATE_FILE):
        with open(LAST_UPDATE_FILE, "r") as f:
            last_update = f.read().strip()
        if last_update == today:
            return
    
    if not os.path.exists(REPO_PATH):
        print("Cloning the repository...")
        subprocess.run(["git", "pull"], check=True)
    else:
        print("Checking for repository updates...", end="| ")
        subprocess.run(["git", "-C", REPO_PATH, "pull"], check=True)
    
    with open(LAST_UPDATE_FILE, "w") as f:
        f.write(today)

def get_first_section_id(project_id):
    """Get the first section ID of the specified project."""
    try:
        sections = api.get_sections(project_id=project_id)
        return sections[0].id if sections else None
    except Exception as e:
        print(f"Error retrieving sections: {e}")
        return None

def add_tasks(task_names, project_id=INBOX_ID):
    """Add multiple tasks to the first section."""
    section_id = get_first_section_id(project_id)
    for task_name in task_names:
        try:
            task = api.add_task(content=task_name, project_id=project_id, section_id=section_id)
            print(f"Task added: {task.id}, {task.content}, Section: {section_id}")
        except Exception as e:
            print(f"Error adding task: {e}")

def get_tasks_in_first_section(project_id=INBOX_ID):
    """Retrieve and display tasks in the first section."""
    section_id = get_first_section_id(project_id)
    if section_id is None:
        print("No section exists.")
        return []

    try:
        tasks = [task for task in api.get_tasks(project_id=project_id) if task.section_id == section_id]
        if not tasks:
            print(f"No tasks in section {section_id}")
            return []

        print(f"Tasks in section {section_id}:")
        for index, task in enumerate(tasks, start=1):
            print(f"- {index}: {task.content}")
        
        return tasks
    except Exception as e:
        print(f"Error retrieving tasks: {e}")
        return []

def complete_tasks(identifiers, project_id=INBOX_ID):
    """Complete the specified tasks by number or name."""
    tasks = get_tasks_in_first_section(project_id)
    if not tasks:
        print("No tasks available to complete.")
        return
    
    id_map = {str(i + 1): task for i, task in enumerate(tasks)}
    name_map = {task.content: task for task in tasks}

    completed, failed = [], []

    for identifier in identifiers:
        task = id_map.get(identifier) or name_map.get(identifier)
        if task:
            try:
                api.close_task(task.id)
                completed.append(task.content)
            except Exception as e:
                failed.append(f"{task.content} (Error: {e})")
        else:
            failed.append(f"{identifier} (Not found)")

    if completed:
        print("Completed tasks:", ", ".join(completed))
    if failed:
        print("Tasks that could not be completed:", ", ".join(failed))

def interactive_shell():
    """Enter interactive shell mode to run commands."""
    print("Todoist Interactive Mode Started (type 'exit' to quit)")
    while True:
        try:
            line = input("todo> ").strip()
            if line.lower() in ("exit", "quit"):
                print("Exiting interactive mode.")
                break
            if not line:
                continue
            args = line.split()
            command = args[0]
            command_args = args[1:]

            if command in ("add", "a"):
                if not command_args:
                    print("Please provide task names to add.")
                    continue
                add_tasks(command_args)
            elif command in ("ls",):
                get_tasks_in_first_section()
            elif command in ("check", "c"):
                if not command_args:
                    print("Please specify task number or name to complete.")
                    continue
                complete_tasks(command_args)
            else:
                print(f"Unknown command: {command}")
        except KeyboardInterrupt:
            print("\nExiting interactive mode (Ctrl+C)")
            break
        except Exception as e:
            print(f"Error occurred: {e}")

def main():
    check_and_update_repo()

    alias_map = {"a": "add", "c": "check"}
    if len(sys.argv) > 1 and sys.argv[1] in alias_map:
        sys.argv[1] = alias_map[sys.argv[1]]

    parser = argparse.ArgumentParser(description="Todoist CLI Tool")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add tasks")
    add_parser.add_argument("task_names", nargs="+", help="Names of the tasks to add")
    add_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="Project ID")

    list_parser = subparsers.add_parser("ls", help="List tasks in the first section")
    list_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="Project ID")

    check_parser = subparsers.add_parser("check", help="Complete a task")
    check_parser.add_argument("identifiers", nargs="+", help="Task number or name to complete")
    check_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="Project ID")

    args = parser.parse_args()

    if args.command == "add":
        add_tasks(args.task_names, args.project_id)
    elif args.command == "ls":
        get_tasks_in_first_section(args.project_id)
    elif args.command == "check":
        complete_tasks(args.identifiers, args.project_id)
    else:
        print("No command specified. Entering interactive mode...")
        interactive_shell()

if __name__ == "__main__":
    main()
