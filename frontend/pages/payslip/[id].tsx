import { useRouter } from 'next/router';
import useSWR from 'swr';
import Layout from '../../components/Layout';

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function PayslipDetail() {
  const router = useRouter();
  const { id } = router.query;
  const { data } = useSWR(id ? `/api/payslip/${id}` : null, fetcher);

  if (!data) return <Layout>読み込み中...</Layout>;

  return (
    <Layout>
      <h1>{data.filename}</h1>
      <p>ID: {data.id}</p>
      {/* 詳細項目編集フォームなどここに */}
    </Layout>
  );
}
