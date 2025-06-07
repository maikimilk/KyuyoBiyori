import useSWR from 'swr';
import Layout from '../components/Layout';
import { Heading, Text, Stack, Stat, StatLabel, StatNumber } from '@chakra-ui/react';

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function Home() {
  const { data } = useSWR('/api/payslip', fetcher);

  return (
    <Layout>
      <Stack spacing={4}>
        <Heading as="h1" size="lg">ダッシュボード</Heading>
        <Stat>
          <StatLabel>アップロード済み明細</StatLabel>
          <StatNumber>{data ? data.length : 0} 件</StatNumber>
        </Stat>
        <Text color="gray.500">グラフやサマリーカードは今後追加予定です。</Text>
      </Stack>
    </Layout>
  );
}
