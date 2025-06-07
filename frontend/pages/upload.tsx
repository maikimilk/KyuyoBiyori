import { useState, useRef } from 'react';
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
  , useToast
} from '@chakra-ui/react';

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement | null>(null);

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
        toast({ status: 'error', title: '通信エラー', description: 'アップロード失敗', isClosable: true });
        setStatus('');
      }
    } catch (e) {
      setError('アップロード失敗');
      toast({ status: 'error', title: '通信エラー', description: 'アップロード失敗', isClosable: true });
      setStatus('');
    } finally {
      setProgress(100);
    }
  };

  const handleFile = (f: File) => {
    setFile(f);
    upload(f);
  };

  const handleCancel = () => {
    setFile(null);
    setPreview(null);
    setError('');
    setStatus('');
    setProgress(0);
    if (inputRef.current) inputRef.current.value = '';
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
        <Flex gap={2} align="center">
          <Input type="file" ref={inputRef} onChange={e => e.target.files && handleFile(e.target.files[0])} />
          <Button onClick={handleCancel}>取り消し</Button>
        </Flex>
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
