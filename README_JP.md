# Todash (Todoist TUI Tool)


<img width="712" height="507" alt="image" src="https://github.com/user-attachments/assets/e6b5a45d-3661-4ccd-9421-aa6cc507b1fd" />

## Overview

Projectの名前をTodoist-CLIからTodashに変えました。
`todo` コマンドで起動するターミナル UI (TUI) で Todoist を操作するツールです。
プロジェクト → セクション → タスクをリスト形式で表示し、**行番号を一番左端**に常時表示します。キーボードだけで快適に管理できます。

## Features
- プロジェクト・セクション・タスクをリスト表示（遅延ロード）
- 全行の左端に行番号を常時表示
- タスクの追加（名前 + 説明）
- タスクの完了・詳細表示・編集
- Undo / Redo（追加・完了・編集操作）
- 他セクションを一括折りたたみ（`Ctrl+w`）
- vim ライクなモードシステム（Normal / Command / Colon / Move）
- 行番号ジャンプ：`Esc → :<N>g → Enter`
- タスク移動モード：`Esc → :mv → Enter`
- 起動時に自動更新チェック（`.env` の `TTY` 秒間隔）
- オプティミスティック UI（処理中のタスクをリアルタイムで薄く表示）

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

## モードシステム

vim ライクなモーダル入力システムを採用しています。

```
Normal ──[Esc]──▶ Command ──[Esc]──▶ Normal
                     │
                    [:]──▶ Colon ──[Esc]──▶ Normal
                     │
                   [:mv]──▶ Move  ──[Esc]──▶ Normal
```

- **Normal**：`j` / `k` と `Enter` で自由に移動
- **Command**：1 キーでアクション（`a`、`Space`、`r`、`e`、`:`）
- **Colon**：コマンドを入力して `Enter`（例：`5g`、`mv`）
- **Move**：目的地のタスクにカーソルを合わせて `Enter`

---

## キー操作

| キー | モード | 動作 |
|---|---|---|
| `j` | 全モード | カーソルを下に移動 |
| `k` | 全モード | カーソルを上に移動 |
| `Enter` | Normal | プロジェクト・セクションを展開 / 折りたたむ |
| `q` | 全モード | アプリを終了 |
| `Esc` | Normal | Command モードへ |
| `Esc` | Command / Colon / Move | Normal モードへ戻る |
| `a` | Command | 現在の場所にタスクを追加 |
| `Space` | Command | 選択中のタスクを完了 |
| `e` | Command | 選択中のタスクを編集 |
| `r` | Command | 現在のプロジェクトを更新 |
| `:` | Command | Colon コマンド入力へ |
| `:<N>g` + `Enter` | Colon | N 行目にジャンプ |
| `:mv` + `Enter` | Colon | 選択中タスクの移動モードへ |
| `Enter` | Move | 目的地タスクの直下に移動を実行 |
| `u` | 全モード | 直前の操作を元に戻す |
| `Ctrl+r` | 全モード | 元に戻した操作をやり直す |
| `Ctrl+w` | 全モード | 現在のセクション以外を折りたたむ |

### 行番号ジャンプ

行番号は常に各行の左端に表示されています。

1. `Esc` を押して Command モードへ
2. `:` を押して Colon モードへ
3. ジャンプしたい行番号に続けて `g` を入力（例：`5g`）し `Enter`
4. `Esc` でキャンセル

### タスク移動

1. 移動したいタスクにカーソルを合わせる
2. `Esc → : → mv → Enter` で移動モードへ（対象タスクが黄色に変わる）
3. 移動先のタスクにカーソルを合わせて `Enter`
4. `Esc` でキャンセル

## License
MIT License
