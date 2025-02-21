import argparse
import os
import subprocess
import datetime
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
    """ Update the repository if it is the first execution of the day """
    today = datetime.date.today().isoformat()
    # Check the last update date
    if os.path.exists(LAST_UPDATE_FILE):
        with open(LAST_UPDATE_FILE, "r") as f:
            last_update = f.read().strip()
        if last_update == today:
            return  # Already updated
    
    # Clone the repository if it does not exist
    if not os.path.exists(REPO_PATH):
        print("Cloning the repository...")
        subprocess.run(["git", "pull"], check=True)
    else:
        print("Checking for repository updates...")
        subprocess.run(["git", "-C", REPO_PATH, "pull"], check=True)
    
    # Record the update date
    with open(LAST_UPDATE_FILE, "w") as f:
        f.write(today)

def get_first_section_id(project_id):
    """ Get the first section ID of the specified project (using cache) """
    try:
        sections = api.get_sections(project_id=project_id)
        return sections[0].id if sections else None
    except Exception as e:
        print(f"Error retrieving sections: {e}")
        return None

def add_task(task_name, project_id=INBOX_ID):
    """ Add a task (add to the first section) """
    section_id = get_first_section_id(project_id)
    try:
        task = api.add_task(content=task_name, project_id=project_id, section_id=section_id)
        print(f"Task added: {task.id}, {task.content}, Section: {section_id}")
    except Exception as e:
        print(f"Error adding task: {e}")

def get_tasks_in_first_section(project_id=INBOX_ID):
    """ Retrieve and display tasks in the first section (minimizing API calls) """
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
    """ Complete the specified tasks by number or name """
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

    # Display the result of processing
    if completed:
        print("Completed tasks:", ", ".join(completed))
    if failed:
        print("Tasks that could not be completed:", ", ".join(failed))

def main():
    check_and_update_repo()  # Check for updates before executing commands
    
    parser = argparse.ArgumentParser(description="Todoist CLI Tool")
    subparsers = parser.add_subparsers(dest="command")

    # Add task (todo add)
    add_parser = subparsers.add_parser("add", help="Add a task")
    add_parser.add_argument("task_name", help="Name of the task to add")
    add_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="Project ID")

    # Get task list (todo ls)
    list_parser = subparsers.add_parser("ls", help="List tasks in the first section")
    list_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="Project ID")

    # Complete task (todo check)
    check_parser = subparsers.add_parser("check", help="Complete a task")
    check_parser.add_argument("identifiers", nargs="+", help="Task number or name to complete")
    check_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="Project ID")

    # Parse arguments
    args = parser.parse_args()

    if args.command == "add":
        add_task(args.task_name, args.project_id)
    elif args.command == "ls":
        get_tasks_in_first_section(args.project_id)
    elif args.command == "check":
        complete_tasks(args.identifiers, args.project_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()