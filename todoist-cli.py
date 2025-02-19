#!/usr/bin/env python

import argparse
import os
from dotenv import load_dotenv
from todoist_api_python.api import TodoistAPI

# .env ファイルの読み込み
load_dotenv()

# グローバル API インスタンスを作成
TODOIST_TOKEN = os.getenv("TODOIST_TOKEN")
INBOX_ID = os.getenv("INBOX_ID")
api = TodoistAPI(TODOIST_TOKEN)

if not TODOIST_TOKEN or not INBOX_ID:
    print("エラー: .env ファイルに TODOIST_TOKEN または INBOX_ID が設定されていません。")
    exit(1)

# セクションを取得する関数（キャッシュを活用）
def get_first_section_id(project_id):
    """ 指定されたプロジェクトの最初のセクションのIDを取得（キャッシュ利用） """
    try:
        sections = api.get_sections(project_id=project_id)
        return sections[0].id if sections else None
    except Exception as e:
        print(f"セクション取得中にエラー: {e}")
        return None

# タスクを追加する関数
def add_task(task_name, project_id=INBOX_ID):
    """ タスクを追加（最初のセクションに追加） """
    section_id = get_first_section_id(project_id)
    try:
        task = api.add_task(content=task_name, project_id=project_id, section_id=section_id)
        print(f"タスク追加: {task.id}, {task.content}, セクション: {section_id}")
    except Exception as e:
        print(f"タスク追加エラー: {e}")

# タスク一覧を取得する関数
def get_tasks_in_first_section(project_id=INBOX_ID):
    """ 最初のセクションのタスクを取得し、表示（API 呼び出しを最小化） """
    section_id = get_first_section_id(project_id)
    if section_id is None:
        print("セクションが存在しません。")
        return []

    try:
        tasks = [task for task in api.get_tasks(project_id=project_id) if task.section_id == section_id]
        if not tasks:
            print(f"セクション {section_id} にタスクなし")
            return []

        print(f"セクション {section_id} のタスク:")
        for index, task in enumerate(tasks, start=1):
            print(f"- {index}: {task.content}")

        return tasks
    except Exception as e:
        print(f"タスク取得エラー: {e}")
        return []

# タスクを一括完了する関数（API 呼び出し最適化）
def complete_tasks(identifiers, project_id=INBOX_ID):
    """ 指定された番号または名前のタスクを完了 """
    tasks = get_tasks_in_first_section(project_id)
    if not tasks:
        print("完了できるタスクがありません。")
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
                failed.append(f"{task.content}（エラー: {e}）")
        else:
            failed.append(f"{identifier}（見つかりませんでした）")

    # 処理結果を表示
    if completed:
        print("完了したタスク:", ", ".join(completed))
    if failed:
        print("完了できなかったタスク:", ", ".join(failed))

# メイン関数
def main():
    parser = argparse.ArgumentParser(description="Todoist CLIツール")
    subparsers = parser.add_subparsers(dest="command")

    # タスク追加（todo add）
    add_parser = subparsers.add_parser("add", help="タスクを追加")
    add_parser.add_argument("task_name", help="追加するタスク名")
    add_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="プロジェクトID")

    # タスク一覧取得（todo li）
    list_parser = subparsers.add_parser("li", help="最初のセクションのタスク一覧")
    list_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="プロジェクトID")

    # タスク完了（todo check）
    check_parser = subparsers.add_parser("check", help="タスクを完了")
    check_parser.add_argument("identifiers", nargs="+", help="完了するタスクの番号または名前")
    check_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="プロジェクトID")

    # 引数解析
    args = parser.parse_args()

    if args.command == "add":
        add_task(args.task_name, args.project_id)
    elif args.command == "li":
        get_tasks_in_first_section(args.project_id)
    elif args.command == "check":
        complete_tasks(args.identifiers, args.project_id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
