import Link from 'next/link';
import { ReactNode } from 'react';

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div>
      <nav style={{ padding: '1rem', borderBottom: '1px solid #ccc' }}>
        <Link href="/" style={{ marginRight: '1rem' }}>ホーム</Link>
        <Link href="/upload" style={{ marginRight: '1rem' }}>アップロード</Link>
        <Link href="/history" style={{ marginRight: '1rem' }}>明細一覧</Link>
        <Link href="/visualize" style={{ marginRight: '1rem' }}>グラフ分析</Link>
        <Link href="/settings" style={{ marginRight: '1rem' }}>設定</Link>
      </nav>
      <main style={{ padding: '1rem' }}>{children}</main>
    </div>
  );
}
