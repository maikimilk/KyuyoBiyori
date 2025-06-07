import { useState } from 'react';
import Layout from '../components/Layout';
import {
  Box,
  Button,
  Flex,
  Heading,
  Image,
  Input,
  Progress,
  SimpleGrid,
  Stack,
  Text
} from '@chakra-ui/react';

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const upload = async (f: File) => {
    setProgress(0);
    setStatus('アップロード中...');
    setError('');
    const form = new FormData();
    form.append('file', f);
    try {
      const res = await fetch('/api/payslip/upload', { method: 'POST', body: form });
      if (res.ok) {
        const data = await res.json();
        setPreview(data);
        setStatus('解析完了');
      } else {
        setError('アップロード失敗');
        setStatus('');
      }
    } catch (e) {
      setError('アップロード失敗');
      setStatus('');
    } finally {
      setProgress(100);
    }
  };

  const handleFile = (f: File) => {
    setFile(f);
    upload(f);
  };

  const handleSave = async () => {
    if (!preview) return;
    await fetch('/api/payslip/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: preview.filename,
        date: preview.date,
        type: preview.type,
        gross_amount: preview.gross_amount,
        net_amount: preview.net_amount,
        deduction_amount: preview.deduction_amount
      })
    });
    setStatus('保存しました');
  };

  return (
    <Layout>
      <Stack spacing={4}>
        <Heading as="h1" size="lg">明細アップロード</Heading>
        <Input type="file" onChange={e => e.target.files && handleFile(e.target.files[0])} />
        {progress > 0 && <Progress value={progress} />}
        {status && <Text>{status}</Text>}
        {error && <Text color="red.500">{error}</Text>}
        {preview && (
          <Box>
            {file && <Image src={URL.createObjectURL(file)} alt="preview" maxW="200px" />}
            <SimpleGrid columns={2} spacing={2} mt={2}>
              {preview.items?.map((it: any, i: number) => (
                <Box key={i} p={2} borderWidth="1px" borderRadius="md">
                  <Text fontWeight="bold">{it.name}</Text>
                  <Text>{it.amount}円</Text>
                </Box>
              ))}
            </SimpleGrid>
            <Flex gap={2} mt={2}>
              <Button colorScheme="teal" onClick={handleSave}>保存</Button>
              <Button onClick={() => file && upload(file)}>再解析</Button>
            </Flex>
          </Box>
        )}
      </Stack>
    </Layout>
  );
}
