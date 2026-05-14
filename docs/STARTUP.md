# 🚀 システム起動手順 — 0 から本稼働まで

このドキュメント通りに進めれば、**約 90 分** で完全稼働します。
各ステップに **「✓ 確認方法」** を入れているので、必ずそれが通ってから次へ進んでください。

---

## ⏱ 全体スケジュール

| Phase | 内容 | 所要時間 |
|---|---|---|
| 0 | アカウント作成・API キー取得 | 45 分 |
| 1 | ローカル設定 | 10 分 |
| 2 | GitHub に公開 | 10 分 |
| 3 | Secrets・権限設定 | 10 分 |
| 4 | 初回動作確認(ドラフト生成) | 5 分 |
| 5 | 初回 note 投稿テスト | 10 分 |
| 6 | 本稼働開始 | (自動) |

---

# Phase 0 — アカウントと API キー(45 分)

> ⚠ **A8.net の提携審査だけは 3-7 日かかります。** 最初に申請を出してしまえば
> 待ち時間中に他の作業ができます。Phase 0 の **最初** に着手してください。

## 0-0. Amazon アソシエイト ID(既存・確認のみ)
- [ ] Amazon アソシエイトの **追跡ID(末尾 `-22`)** を手元に用意
  - 例: `yourname-22`
  - https://affiliate.amazon.co.jp/home → 右上アカウントから ID を確認

> ⚠ **note での Amazon 使用方針**: 本システムは **書籍リコメンド** に限定して
> Amazon リンクを挿入します(家電・雑貨は挿入されません)。各記事に Amazon リンクは
> 1 つだけ、規約準拠の **開示文** (`※Amazonのアソシエイトとして…`) も自動付与されます。

## 0-1. A8.net(最初に申請する)
- [ ] https://www.a8.net/ に登録
- [ ] 「プログラム検索」で以下に **提携申請**(審査 3-7 日):
  - DMM FX / GMO クリック証券 / 外為どっとコム (FX)
  - SBI 証券 / 楽天証券 / マネックス証券 (株)
  - Coincheck / bitFlyer / GMO コイン (暗号資産)
  - ファイナンシャルアカデミー (教育系)
- [ ] 承認されたら各案件の **広告主リンク URL** をメモ(後で `config/affiliate_links.yaml` に貼る)

**✓ 確認方法**: A8.net マイページの「提携中プログラム」に上記が出ていれば OK

---

## 0-2. Anthropic API キー
- [ ] https://console.anthropic.com/ にログイン
- [ ] **Billing → Add credits** で **$20** 入金
- [ ] **API Keys → Create Key**
- [ ] 出てきた `sk-ant-xxx...` を **絶対に閉じる前にコピー**(再表示不可)

**✓ 確認方法**: Billing 残高に $20 が表示されている / キーをメモ帳に保存済

---

## 0-3. OpenAI API キー(DALL-E 用)
- [ ] https://platform.openai.com/api-keys
- [ ] **Billing → Payment method** でクレジットカード登録、**Hard limit を $20/月** に設定
- [ ] **Create new secret key** で `sk-xxx...` を発行・コピー

**✓ 確認方法**: Usage limits 画面に Hard limit: $20.00 が表示されている

---

## 0-4. X (Twitter) Developer
> 💡 **「X アカウントを持っている」だけでは API は使えません。** 既存の X アカウントで
> developer.x.com にログインして **Developer 申請を別途行う必要があります**(Free tier は即時)。
> 投稿主体としたい X アカウントで申請してください(別アカウントで取った API キーは別アカウントの権限になる)。
- [ ] https://developer.x.com/en/portal/dashboard に既存 X アカウントでログイン
- [ ] **Free tier** で Project + App を作成(用途欄は「金融ニュースの自動翻訳・配信」等)
- [ ] App の **Settings → User authentication settings → Set up**:
  - App permissions: **Read and write** ← 必須
  - Type of App: **Web App, Automated App or Bot**
  - Callback URI: `http://localhost`(ダミーで OK)
  - Website URL: 何でも OK
- [ ] **Keys and tokens** タブ:
  - **Consumer Keys** → Regenerate して **API Key / API Secret** をコピー
  - **Authentication Tokens → Access Token and Secret** → Generate
    - 必ず Permissions が **Read and Write** になっていることを確認
  - **Bearer Token** をコピー

**✓ 確認方法**: 5 つの値(API Key / API Secret / Access Token / Access Token Secret / Bearer Token)が手元にある

> ⚠ Access Token が **Read only** で発行されたら、 User authentication settings を Read and write にしてから **必ず Token を再発行** すること。設定変更だけでは反映されない。

---

## 0-4.5. LINE 公式アカウント(任意だが強推奨)
> 💡 **月 5-15 万円のプラットフォーム脱依存収益源**。設定しない場合は LINE CTA が記事に挿入されないだけで、システム自体は動きます。
- [ ] https://www.linebiz.com/jp/entry/ で **LINE 公式アカウント(無料)** を開設
- [ ] LINE Official Account Manager で「友だち追加用 URL」をコピー(`https://lin.ee/xxxxx`)
- [ ] あいさつメッセージとステップ配信(7日間)を作成(GROWTH.md 参照)

**✓ 確認方法**: 友だち追加 URL が手元にある

## 0-5. note アカウント(投稿用・人間アカウント)
- [ ] (既存アカウントあり)プロフィール画像・ヘッダー画像・自己紹介を整える(下記参考)
- [ ] **マガジン機能** で「金融トレンド徹底解剖」というマガジンを 1 つ作成
  - ここに記事を毎日積んでいくと「連載作家」として認識されてフォロー率が上がる

**プロフィール記入の推奨テンプレ**:
```
株 / FX / 暗号資産のトレンドを毎日 10 本深掘り📊
個人投資家のための "今知っておくべき" 情報を 1 万字記事で配信。
気になる方はフォロー推奨🔔
```

**✓ 確認方法**: プロフィール完成 + マガジン 1 つ作成済

---

## 0-6. GitHub アカウント
- [ ] https://github.com/signup
- [ ] (任意)`gh` CLI をインストール: https://cli.github.com/

**✓ 確認方法**: `gh auth status` で認証済表示、または GitHub web にログインできる

---

# Phase 1 — ローカル設定(10 分)

WSL ターミナルで作業します。

## 1-1. プロジェクトに移動
```bash
cd /mnt/c/Users/Owner/trend-article-bot
```

## 1-2. アフィリエイトリンクを実 URL に置換
```bash
# 好きなエディタで開く
nano config/affiliate_links.yaml
# または
code config/affiliate_links.yaml
```

`YOUR_A8_FX_DMM` などのプレースホルダ部分を、A8.net で承認された
**広告主リンク URL** に **全て** 置き換える。

> 💡 まだ提携審査中の案件は、その項目をコメントアウト(行頭に `#`)しておく。

**✓ 確認方法**:
```bash
grep -c 'YOUR_A8' config/affiliate_links.yaml
# 出力が 0 になっていれば全部置換済み
```

## 1-3. (任意) ローカルテストの準備
ローカルで 1 回試したい場合のみ:
```bash
cp .env.example .env
nano .env   # 各 API キーを記入
```

---

# Phase 2 — GitHub に公開(10 分)

## 2-1. Git 初期化
```bash
cd /mnt/c/Users/Owner/trend-article-bot
git init -b main
git add .
git -c user.email="you@example.com" -c user.name="Your Name" commit -m "initial: trend-article-bot"
```

> ⚠ `user.email` / `user.name` を自分のものに置き換えてください。

## 2-2. GitHub に public repo として push

### 方法 A: gh CLI(推奨)
```bash
gh repo create trend-article-bot --public --source=. --remote=origin --push
```

### 方法 B: ブラウザ
1. https://github.com/new で `trend-article-bot` という名前で **public** repo を作成
2. ターミナルに戻って:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/trend-article-bot.git
   git push -u origin main
   ```

**✓ 確認方法**: ブラウザで `https://github.com/YOUR_USERNAME/trend-article-bot` にアクセスして全ファイル(README/src/.github/workflows/等)が見える

---

# Phase 3 — Secrets と権限設定(10 分)

## 3-1. Workflow permissions を Read & Write に
GitHub のリポジトリページで:

1. **Settings**(右上のタブ)
2. 左メニュー **Actions → General**
3. 一番下までスクロール → **Workflow permissions**
4. ✅ **Read and write permissions** を選択
5. **Save**

**✓ 確認方法**: Read and write permissions のラジオボタンがチェック済

## 3-2. Secrets を登録
リポジトリの **Settings → Secrets and variables → Actions → New repository secret** から **下記 9 つ** を全て登録:

| Name | Value(Phase 0 で取得したもの) | 必須 |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | ✅ |
| `OPENAI_API_KEY` | `sk-...` | ✅ |
| `X_API_KEY` | (Consumer API Key) | ✅ |
| `X_API_SECRET` | (Consumer API Secret) | ✅ |
| `X_ACCESS_TOKEN` | (Access Token) | ✅ |
| `X_ACCESS_TOKEN_SECRET` | (Access Token Secret) | ✅ |
| `X_BEARER_TOKEN` | (Bearer Token) | ✅ |
| `AMAZON_AFFILIATE_ID` | `yourname-22`(末尾 `-22` 含む) | 任意 |
| `LINE_OFFICIAL_URL` | `https://lin.ee/xxxxx` | 任意 |

> 💡 `NEWSDATA_API_KEY` は任意(空でも動作する)。
> 💡 `AMAZON_AFFILIATE_ID` 未登録なら Amazon 書籍リンクは挿入されず A8 リンクで埋められます。
> 💡 `LINE_OFFICIAL_URL` 未登録なら LINE CTA は記事に挿入されません。

## 3-3. Variables を登録(運用チューニング用)
同じ画面の **Variables タブ** から **下記 4 つ** を登録(全部任意・デフォルト値あり):

| Name | デフォルト | 説明 |
|---|---|---|
| `FOCUS_CATEGORY` | (空) | `crypto` / `fx` / `stock` を指定すると初期 30 日は 1 カテゴリ集中。空 = 全カテゴリ均等 |
| `BRAND_NAME` | `金融トレンド徹底解剖` | サムネ右下のブランド署名 |
| `DAILY_COST_LIMIT_USD` | `5.0` | 日次 API 上限(超えるとその日の生成は停止) |
| `MONTHLY_COST_LIMIT_USD` | `130.0` | 月次 API 上限(約 ¥20,000)。実測月 $100 + セーフティ |

> 💡 **集中カテゴリモードを推奨**: 初期 30 日は `FOCUS_CATEGORY=crypto` (or `fx`) にセットして「○○の専門家」認識を作るほうがフォロワー伸び率が 3 倍違います。30 日後に空に戻して全カテゴリ展開。

**✓ 確認方法**: Secrets 画面に上記 7 つの行が並んでいる

---

# Phase 4 — 初回動作確認(5 分)

## 4-1. 手動でドラフト生成を 1 回回す
1. GitHub リポジトリ → **Actions** タブ
2. 左メニューから **「Generate Draft Article」** を選択
3. 右上の **「Run workflow」** → **「Run workflow」** を押す
4. 黄色の実行マークが出る → 約 **2-4 分** 待つ → 緑のチェックマークに変わる

**✓ 確認方法**(全部通って初めて Phase 4 成功):
- [ ] Actions の該当 run が **緑(success)** になっている
- [ ] **Issues タブ** に `[DRAFT] 【...】...` という Issue が新規作成されている
- [ ] Issue を開くと **サムネ画像** + **記事本文(折りたたみ)** + **ツイート文プレビュー** が表示される
- [ ] 記事本文の文字数が約 1 万字ある

### 失敗したら
- 赤の × をクリック → Logs を確認
- 多くの場合 Secrets の名前ミス or API クレジット切れ
- 「API key」「401」「insufficient」というキーワードで grep

## 4-2. ニュース翻訳を 1 回回す
1. Actions タブ → **「Translate News and Tweet」**
2. **Run workflow** → 約 1-2 分待つ
3. ✅ 自分の X アカウントに翻訳ニュースが投稿されたら成功

**✓ 確認方法**: 自分の X タイムラインに「絵文字+【日本語見出し】+本文+ハッシュタグ+元記事 URL」のツイートが表示されている

---

# Phase 5 — 初回 note 投稿テスト(10 分)

ここで「半自動運用」の流れを 1 周回します。これが本稼働後の毎日のルーティンです。

## 5-1. Issue を開いて中身を回収
1. Issues タブ → Phase 4-1 で立った `[DRAFT]` の Issue を開く
2. サムネ画像を **右クリック → 画像を保存**
3. 「本文を表示 / 折りたたむ」を展開 → **本文を全選択コピー**

## 5-2. note に投稿
1. https://note.com の右上「投稿」→「テキスト」
2. 本文を **そのままペースト**(Markdown が note 上の見出しに自動変換される)
3. **タイトル** は 1 行目の `# ...` から抜いて、note のタイトル欄に貼る(本文の `# ...` 行は削除)
4. **サムネ画像** をアップロード(記事冒頭のヘッダー画像欄)
5. **マガジン** に「金融トレンド徹底解剖」を選択(0-5 で作ったやつ)
6. 右上 **「公開する」** → 公開設定で **コメント許可・スキ表示 ON** にして公開
7. 公開後の URL(`https://note.com/yourname/n/n01234567`)を **コピー**

## 5-3. Issue にコメントして X 連動を発火
1. Phase 5-1 で開いた Issue に戻る
2. 一番下のコメント欄に **以下の形式** で書き込む:
   ```
   note: https://note.com/yourname/n/n01234567
   ```
3. **Comment** ボタンを押す

## 5-4. 1-2 分後に確認
**✓ 確認方法**:
- [ ] 自分の X タイムラインに「フック+要約+CTA+ハッシュタグ+note URL」の投稿がある
- [ ] X 投稿の URL をクリックすると、Phase 5-2 で公開した note 記事に飛ぶ
- [ ] GitHub Issue が **クローズ** され、「✅ X に投稿しました: https://x.com/...」というコメントが付いている

🎉 ここまで通ったら **完全稼働状態** です。

---

# Phase 6 — 本稼働開始(自動)

これ以降、あなたは何もしなくても以下が回り続けます:

| いつ | 何が起きる | あなたの作業 |
|---|---|---|
| JST 06 時 | **無料**ドラフト Issue 自動生成 | サムネDL→note無料投稿→Issueコメント |
| **JST 07 時** | **有料(¥100)** ドラフト Issue 自動生成 | サムネDL→note有料投稿→Issueコメント |
| JST 08/12 時 | 無料ドラフト | 同上 |
| **JST 14 時** | **有料(¥500)** + Xスレッド版 ドラフト | サムネDL→note有料投稿→Issueコメント |
| JST 17 時 | 無料ドラフト | 同上 |
| JST 19 時 | 無料ドラフト | 同上 |
| **JST 21 時** | **有料(¥500)** + Xスレッド版 ドラフト | サムネDL→note有料投稿→Issueコメント |
| JST 22/23 時 | 無料ドラフト | 同上 |
| JST 07/11/15/19/22/01 時 | 海外ニュース翻訳→X自動投稿 | 不要 |
| **JST 毎週月曜 00 時** | **週次レポート Issue 自動生成** | データ確認&改善反映 |

### tier 内訳(1 日合計)
- 無料: 7 本
- ¥100(入口): 1 本
- ¥500(主力): 2 本(うちプレミアム2本は X スレッド連投で露出最大化)
→ 全部成約なら **1 日 ¥1,100** の販売ポテンシャル(月 ¥33,000)+ アフィリ収益

毎日のあなたの作業 = **約 15-30 分**(10 本 × 1.5 分の note 投稿作業)。

> ⚠ いきなり 10 本/日 はキツいので、最初の 1 週間は **ドラフト Issue の 2-3 本だけ消化** し、残りはスキップで OK。慣れてきたら本数を増やす。
>
> ドラフトを減らしたい場合は `.github/workflows/generate-draft.yml` の cron 行を一部コメントアウト → push で反映。

---

# 🆘 起動時のトラブルシュート

## ❌ Actions の run がそもそも始まらない
- Settings → Actions → General → **Allow all actions** にチェックが入っているか
- `.github/workflows/` 配下の YAML が main ブランチに push されているか

## ❌ ドラフト生成が失敗する
| エラー文 | 原因 | 対処 |
|---|---|---|
| `AuthenticationError 401` | API キーの値が間違い | Secrets を再登録 |
| `insufficient_quota` | Anthropic/OpenAI のクレジット切れ | Console で入金 |
| `ModuleNotFoundError` | requirements.txt の差分が反映されていない | main ブランチに最新が push されているか確認 |
| `403 ... Resource not accessible` | Workflow permissions が Read only | 3-1 を再実施 |

## ❌ X 投稿が失敗する
| エラー文 | 原因 | 対処 |
|---|---|---|
| `403 You currently have access to a subset of X API v2 endpoints` | Access Token が Read only | 0-4 の Authentication tokens を **再発行** |
| `Too Many Requests` | 月 500 投稿上限到達 | 翌月まで待つ / cron 削減 |
| `Duplicate content` | 同じ文を 2 回投げた | 通常は engagement_optimizer の回転で回避されるが、手動 Run を連打すると出る |

## ❌ Issue にコメントしても X に投稿されない
- コメント形式が `note: https://note.com/...` か(コロンの後の半角スペース必須)
- Issue に `auto-draft` ラベルが付いているか
- Actions タブで `Tweet on note Publish` workflow が実行されたか確認

---

# 📋 起動チェックリスト(印刷推奨)

```
Phase 0: アカウント
□ Amazon アソシエイト ID を確認(yourname-22)
□ A8.net 登録 → 各案件に提携申請(3-7日かかる)
□ Anthropic API キー取得 + $20 入金
□ OpenAI API キー取得 + $20 上限設定
□ X Developer Free tier 作成(既存 X アカウントで申請) → Read+Write 権限で 5 つのキー取得
□ note アカウント(既存) + マガジン作成 + プロフィール整備
□ GitHub アカウント

Phase 1: ローカル
□ config/affiliate_links.yaml の YOUR_A8_xxx を全置換

Phase 2: GitHub 公開
□ git init → first commit
□ public repo として push

Phase 3: 設定
□ Workflow permissions: Read and write に変更
□ Secrets を 9 個登録(AMAZON_AFFILIATE_ID + LINE_OFFICIAL_URL 含む)
□ Variables を 4 個登録(FOCUS_CATEGORY 推奨, BRAND_NAME, コスト上限 2 つ)

Phase 4: 動作確認
□ Generate Draft Article を手動実行 → Issue が立つ
□ Translate News and Tweet を手動実行 → X に投稿される

Phase 5: 初回投稿
□ Issue から note に手動投稿
□ Issue に note URL をコメント
□ X 自動投稿が発火 → Issue 自動クローズ

Phase 6: 本稼働
□ ↑ ここまで完了したら自動で回り始める
□ docs/GROWTH.md を読んで「手動でやるべきこと」を毎日 15-30 分実施
```

---

すべて完了したら **`docs/GROWTH.md`** を必ず読んでください。
自動投稿だけではフォロワーは伸びません。プロフィール最適化と日々の手動施策が伸びを決めます。
