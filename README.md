# 給与・賞与明細ビジュアライザーWebアプリ

## 概要

給与明細・賞与明細の画像やPDFをアップロードするだけで、  
「基本給」「手当」「控除」「社会保険」など各項目を自動抽出。  
手取り・額面・控除・賞与推移を**カラフル＆スタイリッシュなグラフで可視化**できるWebアプリです。

---

## 特徴

- **認証なし**ですぐ使える
- **画像/PDFアップロード→Google Cloud Vision APIでOCR自動抽出**
- 「基本給」「手当」「控除」「賞与」などの**自動カテゴリ分け**
- 毎月・毎年の推移を**ワクワクするグラフで可視化**
- **手動修正UI**で誤認識や追加項目も柔軟対応
- **テスト駆動開発**（TDD）スタイル採用
- **SQLite**を初期DBに、**将来はPostgreSQL等への移行も容易な設計**

## ディレクトリ構成

```text
backend/    # FastAPI アプリケーション
  app/      # API実装
  tests/    # pytest テスト
frontend/   # Next.js フロントエンド
```


---

## 技術スタック

- **フロントエンド:**  
  - Next.js (React)
  - Tailwind CSS（スタイリッシュUI）
  - Chart.js/Recharts（カラフルグラフ）

- **バックエンド:**  
  - **FastAPI（Python）**（拡張性・型安全・AI親和性）
    - pytestで自動テスト
    - alembic+SQLAlchemyでDBマイグレーション
  - **データベース:**  
    - SQLite（開発・ローカル用）
    - PostgreSQL（将来的な本番移行用・ORMで柔軟に対応）

- **OCR:**  
  - Google Cloud Vision API

---

## I/O仕様

### 入力
- 画像（JPEG/PNG） or PDFファイル（給与/賞与明細）

### 出力
- 時系列グラフ：額面、手取り、控除推移など
- ダッシュボード：支給内訳・控除内訳・年収・賞与など
- データはユーザーごと・月ごと・カテゴリごとに保存

---

## 給与データの自動カテゴリ例

- **支給項目:** 基本給, 各種手当, 賞与, 残業代, その他
- **控除項目:** 健康保険, 厚生年金, 雇用保険, 所得税, 住民税, その他
- **集計:** 支給合計, 控除合計, 手取り, 口座振込額
- **管理:** 年月, 明細種別, アップロード日

---

## アプリ処理フロー

1. **ファイルアップロード**（画像/PDF）
2. **Google Cloud Vision APIでOCR**
3. **給与明細の構造解析・主要項目抽出（自動パース）**
4. **データベース（SQLite → PostgreSQL移行可）に保存**
5. **ダッシュボードでグラフ表示**
6. **手動編集UIで修正可能**
7. **pytest等による自動テスト**

---

## ローカル開発手順

```bash
# 1. リポジトリクローン
git clone https://github.com/maikimilk/KyuyoBiyori.git
cd KyuyoBiyori

# 2. Python仮想環境（任意）
python -m venv .venv
source .venv/bin/activate

# 3. Google Cloud Vision APIキーを.env.localへ
NEXT_PUBLIC_GCLOUD_API_KEY=xxxxx
# 4. 依存インストール
cd frontend && npm install && cd ..       # フロントエンド依存
pip install -r backend/requirements.txt    # バックエンド依存
# 5. 開発サーバ起動
npm run dev           # フロントエンド
uvicorn backend.app.main:app --reload   # バックエンド（FastAPI）

# 6. ブラウザで http://localhost:3000 へアクセス

# 7. テスト実行例
pytest backend/tests/         # バックエンドテスト
```

## Docker Compose を使った起動

Docker が利用できる環境であれば、フロントエンドとバックエンドをまとめて起動できます。

```bash
docker-compose up --build
```

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000>

フロントエンドからバックエンド API へのアクセスにはリバースプロキシを利用しており
`API_HOST` 環境変数で接続先を指定できます。Docker Compose 起動時は自動で
`http://backend:8000` が設定されます。ローカルで個別に起動する場合は次のように
環境変数を指定してフロントエンドを起動してください。

```bash
API_HOST=http://localhost:8000 npm run dev
```

---

## テスト

* **pytest**でAPI・ロジック単体テスト
* **Jest/React Testing Library**でフロントテスト

---

## 今後の拡張性

* DBマイグレーション: SQLite → PostgreSQLはSQLAlchemy/ORM経由で容易
* AI/LLMによる項目抽出の自動化・精度向上
* 明細フォーマットの柔軟追加（rules管理）
* 認証/クラウド同期、CSVエクスポート、PWA化も順次対応

---

## DBモデル設計（開発者が追記）

> **このセクションに、DBテーブル構造・ORMモデルなどを記述します。
> 例:**

```python
# models.py (SQLAlchemy例)
class Payslip(Base):
    __tablename__ = 'payslips'
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    type = Column(String, nullable=False)  # "給与" or "賞与"
    base_salary = Column(Integer)
    allowance = Column(Integer)
    bonus = Column(Integer)
    total_payment = Column(Integer)
    total_deduction = Column(Integer)
    net_income = Column(Integer)
    health_insurance = Column(Integer)
    pension = Column(Integer)
    tax = Column(Integer)
    ...
    raw_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## API設計（開発者が追記）

> **このセクションに、REST API設計・エンドポイント・サンプルリクエスト/レスポンス例を記述します。
> 例:**

### POST /api/payslip/upload

給与明細画像/PDFのアップロード→解析リクエスト

**リクエスト**

```http
POST /api/payslip/upload
Content-Type: multipart/form-data

file: [JPEG, PNG, PDF]
date: 2025-05
type: "給与"
```

**レスポンス**

```json
{
  "id": 12,
  "date": "2025-05-01",
  "type": "給与",
  "base_salary": 269000,
  "allowance": 12860,
  "total_payment": 356300,
  "total_deduction": 53123,
  "net_income": 303177,
  "details": {
    "health_insurance": 10528,
    "pension": 25260,
    "tax": 6210,
    ...
  }
}
```

---

> **以降、DBモデルやAPI設計を都度追加・更新してください。**

---

## 開発状況

### 現在の主な機能

- Next.js + Chakra UI によるフロントエンド画面（ダッシュボード、アップロード、履歴、設定）
- FastAPI で実装した明細アップロード/保存/一覧取得 API
- 明細データの統計取得、CSV/JSON エクスポート API
- 簡易設定更新 API（テーマカラーなどをメモリ上で管理）
- SQLite と SQLAlchemy を用いたデータ保存
- pytest による API テスト群

### 次の開発アイデア

- Google Cloud Vision API を用いた本格的な OCR 処理
- 認証機能とマルチユーザー対応
- ユーザー設定を DB に保存し永続化
- 機械学習による項目分類精度の向上
- グラフ UI の強化・インタラクティブ編集

## ライセンス

MIT

---

## 開発・設計方針メモ

* DB層はORMで抽象化→DB移行も容易
* 全APIエンドポイントは自動テストを網羅
* フロント・バックエンド分離、OpenAPI対応
* 新規明細フォーマットもrules追加で拡張可
* UI/UXは「楽しく続けられる」体験最優先

---

**給与明細を"楽しく可視化"して人生設計をサポート！
開発メンバー・フィードバック・設計追記も歓迎です。**

\nTODO: detail モードを有効にする手順をここに追記する予定です。
