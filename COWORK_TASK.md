# パーキンソン病 FAQボット セットアップタスク
# Claude Cowork 用タスク指示書
# =============================================
# 使い方：
#   1. このファイルと faq.csv を同じフォルダに置く
#   2. Coworkでそのフォルダを指定
#   3. このファイルの内容をCoworkのチャットに貼り付けて送信
# =============================================

以下のセットアップ作業を順番に実行してください。
各ステップが完了したら報告し、次へ進む前に確認を取ってください。

---

## 前提確認（最初に必ずチェック）

このフォルダに以下のファイルがあることを確認してください：
- `faq.csv`（パーキンソン病FAQデータ、270件）
- `step1_build_index.py`
- `step2_search.py`
- `step3_line_server.py`
- `requirements.txt`

ファイルが不足している場合は作業を止めて報告してください。

---

## Step 1: Python環境の確認とライブラリのインストール

以下を実行してください：

```
python3 --version
```

Python 3.9以上であることを確認してから：

```
pip install -r requirements.txt
```

インストール中にエラーが出た場合は内容を報告してください。
`faiss-cpu` のインストールに失敗する場合は `faiss-cpu==1.7.4` に変更して再試行してください。

完了したら各ライブラリのバージョンを確認して報告してください：
```
pip show sentence-transformers faiss-cpu anthropic line-bot-sdk fastapi
```

---

## Step 2: FAISSインデックスの作成

以下を実行してください：

```
python3 step1_build_index.py
```

### 期待される出力
- `faq.csv` が読み込まれ「FAQ読み込み完了: 270 件」と表示される
- モデル（multilingual-e5-small）が自動ダウンロードされる（初回のみ約130MB）
- ベクトル化が完了する
- `faq.index` と `faq_meta.pkl` が生成される

### エラー時の対処
- `ModuleNotFoundError` → Step 1のインストールをやり直す
- `FileNotFoundError: faq.csv` → faq.csvがこのフォルダにあるか確認する
- メモリ不足エラー → batch_sizeを16に下げて再実行する

完了後、`faq.index` と `faq_meta.pkl` が生成されたことをファイル一覧で確認して報告してください。

---

## Step 3: 動作テスト（Anthropic APIキーが必要）

環境変数にAPIキーをセットしてから：

```
export ANTHROPIC_API_KEY=（あなたのキーをここに入力）
```

テストスクリプトを起動：
```
python3 step2_search.py
```

起動後、以下の3つの質問を順番に入力してテストしてください：

1. `ウェアリングオフとは何ですか？`
2. `レボドパの副作用を教えてください`
3. `パーキンソン病と関係のない質問です`（範囲外の動作確認）

各質問に対して：
- ヒットしたFAQの件数とスコアを確認
- 回答の内容が適切かを確認

テスト完了後 `quit` で終了し、結果を報告してください。

---

## Step 4: .envファイルの作成

以下の内容で `.env` ファイルを作成してください：

```
ANTHROPIC_API_KEY=（あなたのキーをここに入力）
LINE_CHANNEL_SECRET=（LINEのChannel Secretをここに入力）
LINE_CHANNEL_ACCESS_TOKEN=（LINEのChannel Access Tokenをここに入力）
```

**注意：** `.env` ファイルにはキー情報が含まれます。
`.gitignore` に `.env` を追加して、Gitで管理しないようにしてください。

`.gitignore` が存在しない場合は以下の内容で新規作成してください：
```
.env
faq.index
faq_meta.pkl
__pycache__/
*.pyc
```

---

## Step 5: LINEキーの準備状況確認

以下を確認してください：

- [ ] LINE Developersアカウントがあるか
- [ ] Messaging APIチャンネルを作成済みか
- [ ] Channel Secretを取得済みか
- [ ] Channel Access Token（長期）を取得済みか

**未取得の場合** は取得手順を案内します。その旨を報告してください。

取得済みの場合は `.env` にキーを記入して、Step 6へ進んでください。

---

## Step 6: ローカルサーバーの起動テスト

```
export $(cat .env | xargs)
uvicorn step3_line_server:app --host 0.0.0.0 --port 8000
```

ブラウザで以下にアクセスして動作確認：
```
http://localhost:8000/health
```

以下のようなレスポンスが返れば成功です：
```json
{"status": "ok", "faq_count": 270}
```

結果を報告してください。

---

## Step 7: Railwayデプロイ用ファイルの準備

以下の2つのファイルを作成してください。

**Procfile（Railwayの起動コマンド）：**
```
web: uvicorn step3_line_server:app --host 0.0.0.0 --port $PORT
```

**railway.toml（Railway設定）：**
```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn step3_line_server:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
```

作成後、フォルダ内のファイル一覧を確認して報告してください。

---

## 完了報告フォーマット

全ステップ完了後、以下の形式で報告してください：

```
✅ 完了したステップ：Step 1, 2, 3, 4, 6, 7
⚠️  保留中：Step 5（LINEキー未取得）
📁 生成されたファイル：faq.index, faq_meta.pkl, .env, .gitignore, Procfile, railway.toml
🔍 テスト結果：270件のFAQで検索動作確認済み
⏭️  次のアクション：LINE DevelopersでChannel作成 → .envにキーを記入 → railway up
```
