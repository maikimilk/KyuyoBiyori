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
  Text,
  useToast,
  Switch,
  FormControl,
  FormLabel,
} from '@chakra-ui/react';

export default function Upload() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [detailed, setDetailed] = useState(false);
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement | null>(null);

  const upload = async (f: File, monthValue: string, mode: 'simple' | 'detailed') => {
    setProgress(0);
    setStatus('アップロード中...');
    setError('');
    const form = new FormData();
    form.append('file', f);
    form.append('year_month', monthValue);
    form.append('mode', mode);
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
    upload(f, month, detailed ? 'detailed' : 'simple');
  };

  const handleCancel = () => {
    setFile(null);
    setPreview(null);
    setError('');
    setStatus('');
    setProgress(0);
    setMonth(new Date().toISOString().slice(0, 7));
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleSave = async () => {
    if (!preview) return;
    await fetch('/api/payslip/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: preview.filename,
        date: month ? `${month}-01` : preview.date,
        type: preview.type,
        gross_amount: preview.gross_amount,
        net_amount: preview.net_amount,
      deduction_amount: preview.deduction_amount
      })
    });
    setPreview(null);
    setStatus(`保存しました: 総支給額${preview.gross_amount}円 手取り${preview.net_amount}円\n今月もよく頑張りましたね！`);
  };

  return (
    <Layout>
      <Stack spacing={4}>
        <Heading as="h1" size="lg">明細アップロード</Heading>
        <Flex gap={2} align="center" flexWrap="wrap">
          <Input type="file" ref={inputRef} onChange={e => e.target.files && handleFile(e.target.files[0])} />
          <Input type="month" value={month} onChange={e => setMonth(e.target.value)} maxW="180px" />
          <FormControl display="flex" alignItems="center" width="auto">
            <FormLabel htmlFor="detailed" mb="0">詳細解析モード</FormLabel>
            <Switch id="detailed" isChecked={detailed} onChange={e => setDetailed(e.target.checked)} />
          </FormControl>
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
              <Button onClick={() => file && upload(file, month, detailed ? 'detailed' : 'simple')}>再解析</Button>
            </Flex>
          </Box>
        )}
      </Stack>
    </Layout>
  );
}
