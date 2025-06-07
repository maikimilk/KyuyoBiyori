import { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import {
  Box,
  Heading,
  Switch,
  FormControl,
  FormLabel,
  Input,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  IconButton,
  Button,
  Stack,
  Link,
  useColorMode,
} from '@chakra-ui/react';
import { FaPlus, FaTrash } from 'react-icons/fa';

interface Item {
  id: number;
  name: string;
  enabled: boolean;
}

export default function Settings() {
  const { colorMode, toggleColorMode } = useColorMode();
  const [color, setColor] = useState('#319795');
  const [items, setItems] = useState<Item[]>([]);
  const [dragId, setDragId] = useState<number | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem('settings');
    if (stored) {
      const s = JSON.parse(stored);
      if (s.color) setColor(s.color);
      if (s.items) setItems(s.items);
    } else {
      setItems([
        { id: 1, name: '基本給', enabled: true },
        { id: 2, name: '手当', enabled: true },
        { id: 3, name: '控除', enabled: true },
      ]);
    }
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty('--chakra-colors-teal-500', color);
    localStorage.setItem('settings', JSON.stringify({ color, items }));
    fetch('/api/settings/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme_color: color, items, dark_mode: colorMode === 'dark' }),
    }).catch(() => {});
  }, [color, items, colorMode]);

  const addItem = () => {
    const id = Math.max(0, ...items.map(i => i.id)) + 1;
    setItems([...items, { id, name: `項目${id}`, enabled: true }]);
  };

  const updateItem = (id: number, field: keyof Item, value: any) => {
    setItems(items.map(i => (i.id === id ? { ...i, [field]: value } : i)));
  };

  const removeItem = (id: number) => {
    setItems(items.filter(i => i.id !== id));
  };

  const onDragStart = (id: number) => () => setDragId(id);
  const onDragOver = (id: number) => (e: React.DragEvent) => {
    e.preventDefault();
    if (dragId == null || dragId === id) return;
    const from = items.findIndex(i => i.id === dragId);
    const to = items.findIndex(i => i.id === id);
    if (from < 0 || to < 0) return;
    const updated = [...items];
    const [moved] = updated.splice(from, 1);
    updated.splice(to, 0, moved);
    setItems(updated);
    setDragId(id);
  };

  const download = async (fmt: string) => {
    const res = await fetch(`/api/payslip/export?format=${fmt}`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `payslips.${fmt === 'csv' ? 'csv' : 'json'}`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <Layout>
      <Heading as="h1" size="lg" mb={4}>設定</Heading>
      <Stack spacing={6}>
        <FormControl display="flex" alignItems="center" width="auto">
          <FormLabel mb="0">ダークモード</FormLabel>
          <Switch isChecked={colorMode === 'dark'} onChange={toggleColorMode} />
        </FormControl>
        <FormControl width="200px">
          <FormLabel>テーマカラー</FormLabel>
          <Input type="color" value={color} onChange={e => setColor(e.target.value)} p={1} />
        </FormControl>

        <Box>
          <Heading as="h2" size="md" mb={2}>項目管理</Heading>
          <Table size="sm">
            <Thead>
              <Tr><Th>名前</Th><Th>表示</Th><Th></Th></Tr>
            </Thead>
            <Tbody>
              {items.map(it => (
                <Tr key={it.id} draggable onDragStart={onDragStart(it.id)} onDragOver={onDragOver(it.id)}>
                  <Td>
                    <Input value={it.name} onChange={e => updateItem(it.id, 'name', e.target.value)} />
                  </Td>
                  <Td>
                    <Switch isChecked={it.enabled} onChange={e => updateItem(it.id, 'enabled', e.target.checked)} />
                  </Td>
                  <Td>
                    <IconButton aria-label="delete" icon={<FaTrash />} size="sm" onClick={() => removeItem(it.id)} />
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
          <Button leftIcon={<FaPlus />} size="sm" mt={2} onClick={addItem}>追加</Button>
        </Box>

        <Box>
          <Heading as="h2" size="md" mb={2}>データエクスポート</Heading>
          <Stack direction="row">
            <Button onClick={() => download('csv')}>CSV</Button>
            <Button onClick={() => download('json')}>JSON</Button>
          </Stack>
        </Box>

        <Box>
          <Link href="#">サービス利用ガイド</Link>
          <br />
          <Link href="#">プライバシーポリシー</Link>
        </Box>
      </Stack>
    </Layout>
  );
}
