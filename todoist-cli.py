#!/usr/bin/env python

import argparse
import os
from dotenv import load_dotenv
from todoist_api_python.api import TodoistAPI

# .env ファイルの読み込み
load_dotenv()

# 環境変数から API トークンと Inbox ID を取得
TODOIST_TOKEN = os.getenv("TODOIST_TOKEN")
INBOX_ID = os.getenv("INBOX_ID")

if not TODOIST_TOKEN or not INBOX_ID:
    print("エラー: .env ファイルに TODOIST_TOKEN または INBOX_ID が設定されていません。")
    exit(1)

# セクションを取得する関数
def get_first_section_id(project_id):
    """ 指定されたプロジェクトの最初のセクションのIDを取得する """
    api = TodoistAPI(TODOIST_TOKEN)
    try:
        sections = api.get_sections(project_id=project_id)
        if sections:
            return sections[0].id  # 最初のセクションのIDを返す
    except Exception as e:
        print(f"セクション取得中にエラーが発生しました: {e}")
    return None  # セクションがない場合は None を返す

# タスクを追加する関数
def add_task(task_name, project_id=INBOX_ID, section_id=None):
    """ タスクを追加する。セクションが指定されていない場合、最初のセクションを選択 """
    api = TodoistAPI(TODOIST_TOKEN)

    # セクションが指定されていない場合、最初のセクションを取得
    if section_id is None:
        section_id = get_first_section_id(project_id)

    try:
        task = api.add_task(content=task_name, project_id=project_id, section_id=section_id)
        print(f"タスクが追加されました: {task.id}, タスク名: {task.content}, セクションID: {section_id}")
    except Exception as e:
        print(f"タスクの追加中にエラーが発生しました: {e}")

# タスク一覧を取得する関数
def get_tasks_in_first_section(project_id=INBOX_ID):
    """ 指定されたプロジェクトの最初のセクションのタスクを取得し、表示する """
    api = TodoistAPI(TODOIST_TOKEN)

    # 最初のセクションを取得
    section_id = get_first_section_id(project_id)
    if section_id is None:
        print("指定されたプロジェクトにセクションがありません。タスクを取得できません。")
        return

    try:
        tasks = api.get_tasks(project_id=project_id)
        section_tasks = [task for task in tasks if task.section_id == section_id]

        if not section_tasks:
            print(f"セクション ID: {section_id} にはタスクがありません。")
        else:
            print(f"セクション ID: {section_id} のタスク一覧:")
            for index, task in enumerate(section_tasks, start=1):
                print(f"- {index}: {task.content}")

    except Exception as e:
        print(f"タスク取得中にエラーが発生しました: {e}")

# メイン関数
def main():
    parser = argparse.ArgumentParser(description="Todoist CLIツール")
    subparsers = parser.add_subparsers(dest="command")

    # タスク追加コマンド
    add_parser = subparsers.add_parser("add", help="タスクを追加")
    add_parser.add_argument("task_name", help="追加するタスク名")
    add_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="プロジェクトID（デフォルト: Inbox）")
    add_parser.add_argument("-s", "--section_id", help="セクションID（未指定の場合は最初のセクションを使用）")

    # タスク一覧取得コマンド（todo li）
    list_parser = subparsers.add_parser("li", help="最初のセクションのタスクを一覧表示")
    list_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="プロジェクトID（デフォルト: Inbox）")

    # 引数を解析
    args = parser.parse_args()

    # タスク追加
    if args.command == "add":
        add_task(args.task_name, args.project_id, args.section_id)

    # タスク一覧取得
    elif args.command == "li":
        get_tasks_in_first_section(args.project_id)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
