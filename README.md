# 金融トレンド記事 自動生成 → note + X 連動システム

## 🎯 最重要 KPI: フォロワー獲得

本システムは「**note と X のフォロワー数を最大化する**」ことを最重要 KPI として
最適化されています。具体的な施策・期待値・手動でやるべきこと一覧は
👉 **[`docs/GROWTH.md`](docs/GROWTH.md)** を必ず先に読んでください。

---

株 / FX / 暗号資産のトレンドをリアルタイムに検出し、Claude API で 1 万字記事を生成、
サムネを DALL-E 3 で作成、アフィリエイトを内容適合で挿入して GitHub Issue に
ドラフト発行 → 人間が note に承認投稿 → URL を貼り付けると自動で X に投稿される
"半自動" 運用システムです。海外金融ニュースの翻訳 → X 自動投稿 Bot も同梱。

GitHub Actions の cron で 24h 稼働するため、**PC を起動する必要はありません**。

### フォロワー獲得最適化の主な仕掛け
- **タイトル磁力** — 【】+数字+ベネフィットを必ず満たすプロンプト
- **保存価値** — 8 セクション+Q&A+次回予告で「保存される記事」を量産
- **フォロー CTA** — 記事冒頭/末尾に動的に挿入、定型化しない 3 パターン回転
- **連載示唆** — 末尾に「次回予告」を毎回入れてプロフィール訪問動機を作る
- **時間帯最適化** — JST の SNS 接触ピーク(7-9 / 12-13 / 18-22 時)に投稿
- **フック回転** — 8 パターンの引きの強い 1 行目をランダム選択
- **動的ハッシュタグ** — 時間帯+カテゴリで毎回変化、スパム検知を回避
- **クリック誘発サムネ** — 巨大数字+対比強配色+カテゴリバッジで一覧で目立つ

---

## アーキテクチャ

```
┌────────────────────────────────────────────────────────┐
│  GitHub Actions (cron / public repo 無料枠)              │
└─────────┬──────────────────────────┬───────────────────┘
          │                          │
   ┌──────▼──────┐            ┌──────▼──────┐
   │ ①記事ドラフト │            │ ②海外ニュース │
   │   生成        │            │   翻訳→X投稿  │
   │ 2.4h毎 ×10/日 │            │ 4h毎 ×6/日    │
   └──────┬──────┘            └───────────────┘
          │
          ▼
   GitHub Issue としてドラフト発行
   (本文+サムネ+アフィリ込み)
          │
          ▼
   ┌─────────────────────────┐
   │ 人間が note に手動コピペ  │
   │ 投稿 → URL を Issue に    │
   │ コメント                  │
   └──────┬──────────────────┘
          │ (Issue Comment Trigger)
          ▼
   ┌─────────────────────────┐
   │ ③ X へ自動投稿            │
   │   タイトル+note URL       │
   └─────────────────────────┘
```

---

## 月額コスト試算 (1日10本×30日)

| 項目 | 内訳 | 月額 |
|---|---|---|
| Claude API (Sonnet 4.6) | 1万字×10本×30日 | ¥3,000 |
| OpenAI DALL-E 3 | $0.04 × 300枚 | ¥1,800 |
| X API | Free tier(500投稿/月) | ¥0 |
| GitHub Actions | public repoは無制限 | ¥0 |
| ドメイン/その他 | - | ¥0 |
| **合計** | | **約 ¥5,000** |

---

## 必須要件と制約

⚠ **重要 — 規約遵守について**

1. **note の自動投稿は規約違反のリスクがあります。** 本システムは「ドラフト生成までを自動化、最終投稿は人間が承認」の半自動運用としています。完全自動投稿が必要な場合は WordPress への乗り換えを推奨。
2. **note のアフィリエイト規約は流動的です。** `config/affiliate_links.yaml` のリンクを使う前に最新規約を確認してください。Amazonアソシエイトの直リンクは原則NGです。
3. **AI 生成記事の大量投稿はスパム判定対象です。** 1日10本×1万字は note においてはかなり多い投稿数です。アカウント凍結リスクを下げるため、可能なら徐々にペースを上げてください(初週は1日2-3本など)。
4. **X API の Free tier は月500投稿が上限です。** note 連動(10本/日)+ニュース翻訳(6本/日)で約480/月、ギリギリです。

---

## セットアップ

👉 **本番ローンチ Day 0-30 チェックリストは [`docs/LAUNCH_CHECKLIST.md`](docs/LAUNCH_CHECKLIST.md)** ← まずこれ
👉 時系列の起動手順は [`docs/STARTUP.md`](docs/STARTUP.md)(チェックポイント付き)
👉 API キー取得など詳細は [`docs/SETUP.md`](docs/SETUP.md)
👉 フォロワー獲得施策は [`docs/GROWTH.md`](docs/GROWTH.md)
👉 月100万円までの12ヶ月計画は [`docs/ROADMAP_TO_1M.md`](docs/ROADMAP_TO_1M.md)

要点のみ:

1. **このリポジトリをGitHubにpublic repoとしてpush**
2. **必要なAPIキーを取得**
   - Claude API: https://console.anthropic.com/
   - OpenAI API: https://platform.openai.com/
   - X API (Free): https://developer.x.com/
   - A8.net / もしも: アフィリエイト登録
3. **GitHub → Settings → Secrets and variables → Actions** に登録
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY`
   - `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` / `X_BEARER_TOKEN`
   - `A8_AFFILIATE_ID` / `MOSHIMO_AFFILIATE_ID`
4. **`config/affiliate_links.yaml` の `YOUR_A8_xxx` を本物のIDに差し替え**
5. **GitHub Actionsを有効化** → 自動でcron稼働開始

---

## ディレクトリ構成

```
trend-article-bot/
├── .github/workflows/
│   ├── generate-draft.yml      # ①ドラフト生成cron (2.4h毎)
│   ├── news-translate.yml      # ②ニュース翻訳cron (4h毎)
│   └── tweet-on-publish.yml    # ③note URLコメント→X投稿
├── src/
│   ├── trend_scanner.py
│   ├── article_generator.py
│   ├── thumbnail_generator.py
│   ├── affiliate_inserter.py
│   ├── draft_publisher.py
│   ├── tweet_on_publish.py
│   ├── news_translator.py
│   └── x_poster.py
├── prompts/
│   ├── article_system.md       # 記事生成用システムプロンプト
│   ├── thumbnail_prompt.md     # サムネ画像生成用プロンプト
│   └── news_translate.md       # ニュース翻訳用プロンプト
├── config/
│   └── affiliate_links.yaml
├── scripts/
│   └── run_local.py            # ローカルでフルパイプラインをテスト
├── docs/
│   └── SETUP.md
├── requirements.txt
├── .env.example
└── README.md
```

---

## ライセンスと免責

- 本コードは MIT ライセンス相当として配布されます。
- **本システムの利用により生じたnote/Xのアカウント停止、法的問題、その他一切の損害について作者は責任を負いません。** 利用前に必ず各サービスの利用規約を確認してください。
- 金融カテゴリの記事を扱うため、特定商取引法・景品表示法・金融商品取引法に抵触する可能性があります。生成記事は必ず人間が法令適合性を確認してから公開してください。
