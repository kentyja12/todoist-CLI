# Python → Rust 移行計画

## 概要

- **目的**: TUI の高速化・バイナリ配布の簡略化
- **開発環境**: Windows WSL2 (Ubuntu)
- **移行方針**: 機能を維持しつつ段階的に移行。Python 版は移行完了まで並存

---

## 1. WSL 開発環境セットアップ

### 1-1. WSL2 + Ubuntu

```sh
# PowerShell (管理者)
wsl --install -d Ubuntu-24.04
```

### 1-2. Rust ツールチェーン (WSL 内)

```sh
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# stable チャネル選択
source $HOME/.cargo/env
```

### 1-3. ビルド依存ライブラリ (WSL 内)

```sh
sudo apt update
sudo apt install -y build-essential pkg-config libssl-dev
```

### 1-4. エディタ連携

- VS Code: **Remote - WSL** 拡張 + **rust-analyzer** 拡張
- または JetBrains **RustRover** (WSL プロジェクトに対応)

---

## 2. Rust ライブラリ選定

| 役割 | Python | Rust |
|---|---|---|
| TUI フレームワーク | textual | **ratatui** + crossterm |
| HTTP クライアント | requests | **reqwest** (async) |
| 非同期ランタイム | (スレッド) | **tokio** |
| JSON | (組み込み) | **serde** + serde_json |
| 設定ファイル読み込み | python-dotenv | **dotenvy** |
| OS 設定ディレクトリ | os/pathlib | **dirs** |
| インタラクティブ入力 | rich.prompt | **dialoguer** |
| テキストスタイル | rich.text | ratatui の `Span` / `Style` |

---

## 3. プロジェクト構成

```
todoist-CLI/
├── src/
│   ├── main.rs       # エントリポイント・初回セットアップ
│   ├── config.rs     # 設定ファイルのパス管理・読み書き
│   ├── api.rs        # Todoist REST API v1 クライアント
│   ├── app.rs        # アプリ状態・イベントループ
│   ├── ui.rs         # ratatui レンダリング
│   └── types.rs      # Project / Section / Task 型定義
├── Cargo.toml
├── pyproject.toml    # Python 版（移行完了まで残存）
└── todash/           # Python 版（移行完了まで残存）
```

---

## 4. 移行フェーズ

### Phase 1 — プロジェクト初期化・設定管理
- `cargo init` でプロジェクト作成
- `config.rs`: OS 別設定ディレクトリ (`%APPDATA%\todash` / `~/.config/todash`)
- `main.rs`: 初回起動時のセットアップウィザード (`dialoguer`)

**完了条件**: `todo` を初回実行するとトークン入力プロンプトが表示され、設定ファイルに保存される

---

### Phase 2 — API クライアント
- `types.rs`: `Project` / `Section` / `Task` 構造体 (serde Deserialize)
- `api.rs`: 以下のエンドポイントを実装
  - `GET /projects`
  - `GET /sections?project_id=`
  - `GET /tasks?project_id=`
  - `POST /tasks` (追加)
  - `POST /tasks/{id}` (編集)
  - `POST /tasks/{id}/close`
  - `POST /tasks/{id}/reopen`
  - `POST /tasks/{id}/move`
  - `DELETE /tasks/{id}`
  - ページネーション (`next_cursor`) 対応

**完了条件**: API 呼び出しが正常に動作し、データ取得できる

---

### Phase 3 — TUI 骨格
- `ratatui` + `crossterm` のセットアップ
- `app.rs`: `App` 構造体に `projects_data` / `flat_nodes` / `mode` を定義
- イベントループ: キー入力 → `app.on_key()` → 再描画
- `ui.rs`: 行番号付きリスト表示 (`{n:>3}│ ...`)

**完了条件**: プロジェクト一覧が行番号付きで表示される

---

### Phase 4 — ツリー操作
- プロジェクト展開・折りたたみ (Enter)
- セクション展開・折りたたみ
- `j` / `k` カーソル移動
- `flat_nodes` の再構築ロジック

**完了条件**: プロジェクトを展開してタスク一覧を閲覧できる

---

### Phase 5 — Vim ライクモード
- Normal / Command / Colon / Move モード切り替え
- `Esc` → コマンドモード
- `:Ng` 行ジャンプ
- `:mv` 移動モード開始
- モードインジケーター表示

**完了条件**: Python 版と同じキー操作が動作する

---

### Phase 6 — タスク操作モーダル
- ratatui にはモーダルの組み込みサポートがないため、オーバーレイとして実装
- `AddTask` モーダル: タスク名・説明入力
- `EditTask` モーダル: 既存タスク編集

**完了条件**: タスクの追加・編集が動作する

---

### Phase 7 — 非同期 API 呼び出し・楽観的 UI
- `tokio::spawn` で API 呼び出しをバックグラウンド実行
- 送信中タスクを `pending` 状態で薄表示
- 成功/失敗で UI 更新

**完了条件**: API 通信中も UI がブロックされない

---

### Phase 8 — Undo / Redo
- `undo_stack` / `redo_stack` を `Vec` で管理
- 各操作に `undo_fn` / `redo_fn` を持たせる (`Box<dyn Fn>`)
- `u` / `Ctrl+R` でスタック操作

**完了条件**: タスク追加・完了・編集の Undo/Redo が動作する

---

### Phase 9 — パッケージング・配布
- `cargo build --release` でシングルバイナリ生成
- インストール方法:
  ```sh
  cargo install --path .
  ```
- 将来的に `cargo-dist` で GitHub Releases へバイナリ配布

**完了条件**: `cargo install --path .` で `todo` コマンドがどこからでも実行できる

---

## 5. Python 版の扱い

| タイミング | アクション |
|---|---|
| Phase 1〜8 実装中 | Python 版 (`todash/`) を並存。`pyproject.toml` も維持 |
| Phase 9 完了・動作確認後 | Python 版ファイル (`todash/`, `pyproject.toml`) を削除 |

---

## 6. 想定スケジュール

| Phase | 作業量の目安 |
|---|---|
| WSL 環境セットアップ | 0.5 日 |
| Phase 1–2 | 1〜2 日 |
| Phase 3–4 | 2〜3 日 |
| Phase 5–6 | 2〜3 日 |
| Phase 7–8 | 2〜3 日 |
| Phase 9 | 0.5 日 |
| **合計** | **約 8〜12 日** |

---

## 7. 確認事項

移行前にご確認ください：

1. **WSL のバージョン**: すでに WSL2 がインストールされていますか？
2. **`todo` コマンド名**: Rust 版でも同じ `todo` を使いますか？
3. **ratatui のモード**: ratatui は同期描画が基本ですが、`tokio` との組み合わせ (`ratatui` + `tokio`) で非同期対応します。この方針でよいですか？
