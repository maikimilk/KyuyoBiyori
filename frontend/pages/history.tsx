import useSWR from 'swr';
import Layout from '../components/Layout';

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function History() {
  const { data } = useSWR('/api/payslip', fetcher);

  return (
    <Layout>
      <h1>明細一覧</h1>
      <ul>
        {data?.map((p: any) => (
          <li key={p.id}>
            <a href={`/payslip/${p.id}`}>{p.filename}</a>
          </li>
        ))}
      </ul>
    </Layout>
  );
}
