# Todoist CLI Tool

<img width="712" height="507" alt="image" src="https://github.com/user-attachments/assets/e6b5a45d-3661-4ccd-9421-aa6cc507b1fd" />

## Overview
`todo` コマンドで起動するターミナル UI (TUI) で Todoist を操作するツールです。
プロジェクト → セクション → タスクをツリー形式で表示し、キーボードだけで快適に管理できます。

## Features
- プロジェクト・セクション・タスクをツリー表示（遅延ロード）
- タスクの追加（名前 + 説明）
- タスクの完了・詳細表示・編集
- Undo / Redo（追加・完了・編集操作）
- 他セクションを一括折りたたみ
- vim ライクな行番号ジャンプ
- 起動時に自動更新チェック（`.env` の `TTY` 秒間隔）

## Requirements
- Python 3.10 以上
- [Todoist API トークン](https://developer.todoist.com/appconsole)

## Installation

### 1. リポジトリをクローン
```sh
git clone https://github.com/kentyja12/todoist-CLI.git
cd todoist-CLI
```

### 2. 仮想環境を作成して依存パッケージをインストール
```sh
python -m venv .env
# Windows
.env\Scripts\activate
# macOS / Linux
source .env/bin/activate

pip install -r requirements.txt
```

### 3. `.env` ファイルを作成
```
TODOIST_TOKEN=your_todoist_api_token
TTY=300
```

- `TODOIST_TOKEN`: Todoist の API トークン（必須）
- `TTY`: 自動更新間隔（秒）。省略時は 3600 秒

---

## `todo` コマンドの登録

### Windows (PowerShell)

`todo.bat` を作成してパスの通ったフォルダに置きます。

```bat
@echo off
C:\path\to\.env\Scripts\python.exe C:\path\to\todoist-CLI\todoist-cli.py %*
```

### macOS / Linux

```sh
#!/bin/bash
/path/to/.env/bin/python /path/to/todoist-CLI/todoist-cli.py "$@"
```

`~/bin/todo` 等に置いて `chmod +x` を実行してください。

---

## キー操作

| キー | 画面表示 | 動作 |
|---|---|---|
| `a` | Add Task | タスクを追加 |
| `Space` | Complete | タスクを完了 |
| `Enter` | — | タスクの詳細を表示・編集 |
| `u` | Undo | 元に戻す |
| `Ctrl+r` | Redo | やり直し |
| `Ctrl+w` | Collapse Others | 現在のセクション以外を折りたたむ |
| `g` | Jump | 行番号ジャンプモード |
| `r` | Refresh | 現在のプロジェクトを更新 |
| `q` | Quit | 終了 |

### 行番号ジャンプ（`g`）

1. `g` を押すと全可視ノードに番号が表示される
2. ジャンプしたい番号を入力して `Enter`
3. `Esc` でキャンセル

## License
MIT License
