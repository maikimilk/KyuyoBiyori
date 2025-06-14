# 給与・賞与明細ビジュアライザー Web アプリ "KyuyoBiyori"

## 全体の概要

KyuyoBiyori は、給与や賞与の明細画像・PDF をアップロードするだけで、
金額や項目を自動で抽出し、手取り額や控除額の推移をグラフ化する Web アプリです。
OCR には Google Cloud Vision API を利用し、抽出結果を FastAPI + SQLite
(将来的には PostgreSQL) へ保存します。Next.js + Chakra UI のフロントエンドを備え、
手軽に給与データを可視化できます。

## 特徴

- 認証なしですぐ使えるシンプルな UI
- 画像/PDF アップロード → Vision API で OCR 自動抽出
- "支給" と "控除" を自動分類しグラフ化
- 手動修正 UI で誤認識を補正可能
- pytest によるテスト駆動開発

## ディレクトリ構成

```text
backend/        FastAPI アプリケーション
  app/          API 実装一式
    routers/    エンドポイント
    ocr/        OCR パーサ
    domain/     ドメインモデル
    schemas/    Pydantic スキーマ
  tests/        pytest テスト
frontend/       Next.js + Chakra UI フロントエンド
  pages/        画面 (ダッシュボードなど)
  components/   React コンポーネント
docker-compose.yml
```

## 技術スタック

- **フロントエンド:** Next.js (React), TypeScript, Chakra UI, Chart.js
- **バックエンド:** FastAPI, SQLAlchemy, Pydantic, pytest
- **データベース:** SQLite (開発用) / PostgreSQL (将来移行想定)
- **OCR:** Google Cloud Vision API

## I/O仕様

### 入力
- JPEG/PNG 画像または PDF の給与・賞与明細

### 出力
- 月次・年次の支給額/控除額/手取り額グラフ
- 支給内訳・控除内訳の表

## 写真からの割り振り例

アップロードされた明細から以下のような項目を自動抽出します。

- **支給項目:** 基本給, 各種手当, 賞与, 残業代 など
- **控除項目:** 健康保険, 厚生年金, 雇用保険, 所得税, 住民税 など
- **集計:** 支給合計, 控除合計, 差引支給額

## アプリフロー

1. 画像/PDF をアップロード
2. Vision API で OCR を実行
3. 抽出結果をパースして DB へ保存
4. ダッシュボードでグラフ表示
5. 必要に応じて手動編集

## DBモデル設計

主要テーブルは次の通りです。（抜粋）

```python
class Payslip(Base):
    __tablename__ = 'payslips'
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=True)
    type = Column(String, nullable=True)  # salary / bonus
    filename = Column(String, nullable=False)
    gross_amount = Column(Integer, nullable=True)
    net_amount = Column(Integer, nullable=True)
    deduction_amount = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    items = relationship("PayslipItem", back_populates="payslip", cascade="all, delete-orphan")

class PayslipItem(Base):
    __tablename__ = 'payslip_items'
    id = Column(Integer, primary_key=True, index=True)
    payslip_id = Column(Integer, ForeignKey('payslips.id'))
    name = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    category = Column(String, nullable=True)
```

## API設計

一部エンドポイントを紹介します。

| メソッド | パス | 内容 |
|---|---|---|
| `POST` | `/api/payslip/upload` | 明細画像/PDF のアップロード・解析 |
| `POST` | `/api/payslip/save` | 解析結果の保存 |
| `GET`  | `/api/payslip/` | 登録済み明細の一覧取得 |
| `GET`  | `/api/payslip/summary` | 今月と先月の比較など統計取得 |
| `GET`  | `/api/payslip/stats` | 月別・年別集計データ取得 |
| `GET`  | `/api/payslip/breakdown` | 年度別の項目内訳取得 |
| `DELETE` | `/api/payslip/delete` | 明細の削除 |

## 開発状況

- フロントエンド画面（ダッシュボード・アップロード等）を実装済み
- 基本的な API と SQLite 保存が動作
- 詳細解析モードや設定更新 API を搭載
- 今後は Vision API を用いた OCR 強化や認証機能を検討中

## 開発指針

- ORM で DB を抽象化し将来の移行を容易に
- API には必ず自動テストを追加
- フロント/バックエンドは明確に分離し OpenAPI ドキュメントを活用
- UI/UX は "楽しく続けられる" 体験を重視

## ローカルでの開発方法

```bash
# 1. リポジトリ取得
git clone https://github.com/maikimilk/KyuyoBiyori.git
cd KyuyoBiyori

# 2. Python 仮想環境（任意）
python -m venv .venv
source .venv/bin/activate

# 3. 依存関係インストール
cd frontend && npm install && cd ..
pip install -r backend/requirements.txt

# 4. 環境変数に Vision API キーを設定
export GOOGLE_APPLICATION_CREDENTIALS=path/to/gcp_key.json

# 5. 開発サーバ起動
npm --prefix frontend run dev
uvicorn backend.app.main:app --reload
```

Docker Compose でもフロントエンド (port 3000) とバックエンド (port 8000) をまとめて起動できます。

---

MIT License
