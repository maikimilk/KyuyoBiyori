import Layout from '../components/Layout';
import { Heading, Text } from '@chakra-ui/react';

export default function Visualize() {
  return (
    <Layout>
      <Heading as="h1" size="lg" mb={4}>グラフ分析</Heading>
      <Text color="gray.500">グラフ描画機能は今後追加予定です。</Text>
    </Layout>
  );
}
