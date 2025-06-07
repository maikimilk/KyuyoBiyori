import useSWR from 'swr';
import Layout from '../components/Layout';
import { Heading, List, ListItem, Link } from '@chakra-ui/react';

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function History() {
  const { data } = useSWR('/api/payslip', fetcher);

  return (
    <Layout>
      <Heading as="h1" size="lg" mb={4}>明細一覧</Heading>
      <List spacing={2}>
        {data?.map((p: any) => (
          <ListItem key={p.id}>
            <Link href={`/payslip/${p.id}`} color="teal.500">{p.filename}</Link>
          </ListItem>
        ))}
      </List>
    </Layout>
  );
}
