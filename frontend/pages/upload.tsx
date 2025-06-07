import { useState } from 'react';
import Layout from '../components/Layout';
import { Heading, Input, Button, Text, Stack } from '@chakra-ui/react';

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState('');

  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/payslip/upload', { method: 'POST', body: formData });
    if (res.ok) {
      setMessage('アップロードしました');
    } else {
      setMessage('アップロード失敗');
    }
  };

  return (
    <Layout>
      <Stack spacing={4}>
        <Heading as="h1" size="lg">明細アップロード</Heading>
        <Input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
        <Button onClick={handleUpload} colorScheme="teal">送信</Button>
        {message && <Text>{message}</Text>}
      </Stack>
    </Layout>
  );
}
