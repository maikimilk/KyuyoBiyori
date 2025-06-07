import { useRouter } from 'next/router';
import useSWR from 'swr';
import Layout from '../../components/Layout';
import { Heading, Text, Stack } from '@chakra-ui/react';

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function PayslipDetail() {
  const router = useRouter();
  const { id } = router.query;
  const { data } = useSWR(id ? `/api/payslip/${id}` : null, fetcher);

  if (!data) return <Layout>読み込み中...</Layout>;

  return (
    <Layout>
      <Stack spacing={4}>
        <Heading as="h1" size="lg">{data.filename}</Heading>
        <Text>ID: {data.id}</Text>
        <Text color="gray.500">詳細項目編集フォームは今後追加予定です。</Text>
      </Stack>
    </Layout>
  );
}
