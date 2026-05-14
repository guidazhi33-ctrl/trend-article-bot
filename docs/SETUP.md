# セットアップ手順 — 0 から本番稼働まで

このドキュメント通りに進めると、約 60〜90 分で完全稼働まで到達できます。

---

## 0. 全体像

必要なアカウント:
- [ ] GitHub (無料)
- [ ] Anthropic Console — Claude API
- [ ] OpenAI Platform — DALL-E 3
- [ ] X Developer Portal — Free tier
- [ ] note (記事公開用、人間アカウント)
- [ ] A8.net / もしもアフィリエイト など

---

## 1. ローカルにこのプロジェクトを取得

```bash
# 既に /mnt/c/Users/Owner/trend-article-bot に展開されています
cd /mnt/c/Users/Owner/trend-article-bot
```

## 2. GitHub に **public** リポジトリとして push

> ⚠ public にする理由: GitHub Actions の cron は **public repo は無制限無料**、 private だと月 2000 分上限あり。1日10回×記事生成 ≒ 50分/日 ≒ 1500分/月でギリギリ枠内ですが、念のため public 推奨。

```bash
git init -b main
git add .
git commit -m "initial commit: trend-article-bot"
gh repo create trend-article-bot --public --source=. --remote=origin --push
```

(`gh` が無い場合は GitHub UI で repo を作って `git remote add origin ...` → `git push`)

## 3. API キー取得

### 3-1. Anthropic API キー
1. https://console.anthropic.com/ にログイン
2. 「API Keys」→「Create Key」
3. **クレジットを最低 $20 入れておく**(従量課金開始のため)
4. キー(`sk-ant-...`)をコピー

### 3-2. OpenAI API キー
1. https://platform.openai.com/api-keys
2. キー(`sk-...`)を発行
3. Billing → Payment method を登録、$10 程度の上限を設定

### 3-3. X (Twitter) API
1. https://developer.x.com/en/portal/dashboard
2. Free tier で「Create App」
3. **App settings → User authentication settings**
   - App permissions: **Read and write**
   - Type of App: **Web App**
4. Keys & tokens:
   - **API Key** / **API Secret** (Consumer Keys) を発行
   - **Access Token** / **Access Token Secret** を発行
   - **Bearer Token** をコピー
5. 注意: Free tier の月 500 投稿(=月の天井) を必ず守る運用にすること。

### 3-4. アフィリエイト
- A8.net (https://www.a8.net/) に登録
- 金融カテゴリ(FX/証券/暗号資産) の主要案件(例: DMM FX、SBI証券、Coincheck)に提携申請
- 各案件の **広告主専用リンク URL** をメモ
- `config/affiliate_links.yaml` の `YOUR_A8_xxx` プレースホルダを実際の URL に書き換え

```bash
# vim や好きなエディタで
$EDITOR config/affiliate_links.yaml
```

## 4. GitHub Secrets に登録

リポジトリページ → **Settings → Secrets and variables → Actions → New repository secret**。

| Secret name | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `OPENAI_API_KEY` | `sk-...` |
| `X_API_KEY` | (X の API Key) |
| `X_API_SECRET` | (X の API Secret) |
| `X_ACCESS_TOKEN` | (X の Access Token) |
| `X_ACCESS_TOKEN_SECRET` | (X の Access Token Secret) |
| `X_BEARER_TOKEN` | (X の Bearer Token) |
| `AMAZON_AFFILIATE_ID` | (例: `yourname-22`、末尾 `-22` 含む) |
| `NEWSDATA_API_KEY` | (任意、未使用なら空でOK) |

## 5. Actions を有効化

リポジトリページ → **Settings → Actions → General**
- "Allow all actions and reusable workflows" を選択
- "Workflow permissions" → **"Read and write permissions"** を選択
- "Allow GitHub Actions to create and approve pull requests" は不要

## 6. 動作確認 (1 本だけ手動実行)

リポジトリ → **Actions タブ → "Generate Draft Article" → "Run workflow"**

数分後、以下が起きるはず:
1. `drafts/<timestamp>-<slug>/` ブランチに article.md + thumbnail.png が commit される
2. `[DRAFT] {{title}}` という Issue が立つ
3. Issue 本文にサムネと記事全文(折りたたみ)が表示される

## 7. 初回の投稿フロー

1. Issue を開き、サムネ画像を右クリック→保存
2. 記事本文を折りたたみから展開してコピー
3. note の編集画面で新規記事を作成し、本文をペースト・サムネをアップロード
4. note で「公開」→ できた URL をコピー(例: `https://note.com/yourname/n/n01234567`)
5. **Issue にコメント** で以下を投稿:
   ```
   note: https://note.com/yourname/n/n01234567
   ```
6. 1〜2 分後、自動で X に投稿され、Issue がクローズされる
7. X の投稿に note URL が含まれていることを確認

## 8. ニュース翻訳 Bot のテスト

リポジトリ → **Actions タブ → "Translate News and Tweet" → "Run workflow"**

X タイムラインに翻訳ツイートが投稿されるはず。
初回は `news-state` ブランチが自動作成され、以降そこに state が保存される。

## 9. 本番運用に入る

- ドラフト生成: 1 日 10 回(UTC cron) 自動で走る
- ニュース翻訳: 1 日 6 回(4 時間毎) 自動で走る
- あなたは Issue が立つたびに承認 → note 投稿 → URL コメントするだけ

---

## トラブルシュート

### Issue が立たない
- `Actions` タブで該当 workflow の log を確認
- `GH_TOKEN` の `Read and write permissions` が必須

### X 投稿が失敗する
- Free tier の月 500 投稿上限に到達していないか
- App permissions が "Read and write" か(取得し直しが必要なことも)
- レート制限: 短時間に大量投稿でブロックされることあり

### Claude API のコストが高くなる
- `src/article_generator.py` の `MODEL = "claude-sonnet-4-6"` を変更しない(Opus は数倍高い)
- 「Stage 3 expand」が頻発するなら `target_chars` を 8000 に下げる
- それでも高い場合 1 日の cron 回数を 10 → 5 に減らす(`.github/workflows/generate-draft.yml`)

### note にアフィリエイトを貼ったら警告された
- note の規約を再確認。A8.net 経由でも特定カテゴリは NG の場合あり
- WordPress へ完全移行を検討(本プロジェクトは将来拡張余地として準備済み)

### サムネが英語フォントになる
- GitHub Actions の `Install Japanese fonts` step が失敗していないか確認
- ローカル実行時は `apt install fonts-noto-cjk` (Ubuntu) / Yu Gothic 等を導入

---

## コスト監視

- Anthropic Console → Usage で日次のコストをチェック(目安 ¥100/日)
- OpenAI Platform → Usage で同様
- 想定を超え始めたら cron の頻度を下げる

---

## 拡張アイデア

- WordPress 並列投稿(`src/wordpress_publisher.py` を追加し、xmlrpc で投稿)
- Discord/Slack に「ドラフト完成しました」通知
- 投稿後の note PV を計測して人気記事だけ X 再投稿
- A/B テスト: 同じトレンドで 2 種類のタイトル生成 → 反応の良い方だけ採用
