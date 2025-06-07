import Layout from '../components/Layout';
import { Heading, Text } from '@chakra-ui/react';

export default function Settings() {
  return (
    <Layout>
      <Heading as="h1" size="lg" mb={4}>設定</Heading>
      <Text color="gray.500">設定項目は今後追加予定です。</Text>
    </Layout>
  );
}
