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
def get_sections(project_id):
    api = TodoistAPI(TODOIST_TOKEN)
    try:
        return api.get_sections(project_id=project_id) 
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return []

# タスクを追加する関数
def add_task(task_name, project_id=INBOX_ID, section_id=None):
    api = TodoistAPI(TODOIST_TOKEN)
    try:
        task = api.add_task(content=task_name, project_id=project_id, section_id=section_id)
        print(f"タスクが追加されました: {task.id}, タスク名: {task.content}")
    except Exception as e:
        print(f"タスクの追加中にエラーが発生しました: {e}")

# メイン関数
def main():
    parser = argparse.ArgumentParser(description="Todoist CLIツール")
    
    subparsers = parser.add_subparsers(dest="command", help="コマンドを指定してください")

    # セクション一覧取得コマンド
    section_parser = subparsers.add_parser("section", help="セクション一覧を取得")
    section_parser.add_argument("li", action="store_true", help="セクション一覧を取得します")
    section_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="プロジェクトID（デフォルト: Inbox）")

    # タスク追加コマンド
    add_parser = subparsers.add_parser("add", help="タスクを追加")
    add_parser.add_argument("task_name", help="追加するタスク名")
    add_parser.add_argument("-p", "--project_id", default=INBOX_ID, help="プロジェクトID（デフォルト: Inbox）")
    add_parser.add_argument("-s", "--section", help="セクション名またはセクションID（未指定の場合は最初のセクションを使用）")

    # 引数を解析
    args = parser.parse_args()

    # セクション一覧取得
    if args.command == "section" and args.li:
        get_sections(args.project_id)

    # タスク追加
    elif args.command == "add":
        section_id = None
        sections = get_sections(args.project_id)  # 指定されたプロジェクトのセクション一覧を取得

        # セクションが指定されていない場合は最初のセクションを使用
        if not args.section and sections:
            section_id = sections[0].id
            print(f"セクションが指定されていないため、デフォルトで最初のセクション '{sections[0].name}' を使用します。")
        elif args.section:
            # 指定されたセクション名またはIDを確認
            for section in sections:
                if args.section == section.name or args.section == section.id:
                    section_id = section.id
                    break
            if section_id is None:
                print(f"指定されたセクション '{args.section}' が見つかりませんでした。セクションなしで進みます。")

        add_task(args.task_name, args.project_id, section_id)

    # 無効なコマンド
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
