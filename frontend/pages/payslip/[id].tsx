import { useRouter } from 'next/router';
import useSWR from 'swr';
import { useEffect, useState } from 'react';
import Layout from '../../components/Layout';
import {
  Heading,
  Text,
  Stack,
  Flex,
  Box,
  Input,
  NumberInput,
  NumberInputField,
  Select,
  Button,
  Badge,
} from '@chakra-ui/react';

const fetcher = (url: string) => fetch(url).then(r => r.json());

interface Item {
  id?: number;
  name: string;
  amount: number;
  category?: string;
}

export default function PayslipDetail() {
  const router = useRouter();
  const { id } = router.query as { id?: string };
  const { data } = useSWR(id ? `/api/payslip/${id}` : null, fetcher);
  const [items, setItems] = useState<Item[]>([]);
  const [orig, setOrig] = useState<Item[]>([]);

  useEffect(() => {
    if (data) {
      setItems(data.items || []);
      setOrig(data.items || []);
    }
  }, [data]);

  const updateItem = (idx: number, field: keyof Item, value: any) => {
    setItems(items.map((it, i) => (i === idx ? { ...it, [field]: value } : it)));
  };

  const addRow = () => setItems([...items, { name: '', amount: 0, category: '' }]);
  const deleteRow = (idx: number) => setItems(items.filter((_, i) => i !== idx));

  const reparse = async () => {
    const res = await fetch('/api/payslip/reparse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items }),
    });
    if (res.ok) {
      setItems(await res.json());
    }
  };

  const undo = () => setItems(orig);

  const save = async () => {
    if (!data) return;
    if (items.some(it => !it.category || it.amount === undefined || it.amount === null)) {
      alert('未分類または金額未入力の項目があります');
      return;
    }
    const res = await fetch('/api/payslip/update', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...data, items }),
    });
    if (res.ok) {
      router.push('/history');
    }
  };

  if (!data) return <Layout>読み込み中...</Layout>;

  return (
    <Layout>
      <Stack spacing={4}>
        <Heading as="h1" size="lg">{data.filename}</Heading>
        {data.warnings && data.warnings.length > 0 && (
          <Badge colorScheme="red">⚠ 内訳と合計が一致しません</Badge>
        )}
        <Flex gap={4} align="flex-start" direction={{ base: 'column', md: 'row' }}>
          <Box flex="1" minW="200px">
            <Text color="gray.500">画像表示は未実装</Text>
          </Box>
          <Box flex="1">
            {items.map((it, idx) => (
              <Flex key={idx} gap={2} mb={2} align="center" bg={!it.category || it.amount === undefined ? 'yellow.100' : undefined} p={2} borderRadius="md">
                <Input value={it.name} onChange={e => updateItem(idx, 'name', e.target.value)} placeholder="項目名" />
                <NumberInput value={it.amount} onChange={(_, v) => updateItem(idx, 'amount', v)} maxW="100px">
                  <NumberInputField />
                </NumberInput>
                <Select placeholder="カテゴリ" value={it.category || ''} onChange={e => updateItem(idx, 'category', e.target.value)} maxW="120px">
                  <option value="payment">支給</option>
                  <option value="deduction">控除</option>
                </Select>
                <Button size="sm" onClick={() => deleteRow(idx)}>削除</Button>
              </Flex>
            ))}
            <Button size="sm" onClick={addRow} mt={2}>追加</Button>
            <Flex gap={2} mt={4} flexWrap="wrap">
              <Button onClick={reparse}>AI再解析</Button>
              <Button onClick={undo}>元に戻す</Button>
              <Button colorScheme="teal" onClick={save}>保存</Button>
              <Button onClick={() => router.back()}>キャンセル</Button>
            </Flex>
          </Box>
        </Flex>
      </Stack>
    </Layout>
  );
}
