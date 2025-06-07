import { useState, useMemo } from 'react';
import useSWR from 'swr';
import Layout from '../components/Layout';
import {
  Heading,
  Stack,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Select,
  Input,
  Tag,
  IconButton,
  Button,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
} from '@chakra-ui/react';
import { DeleteIcon, CopyIcon, EditIcon, ViewIcon } from '@chakra-ui/icons';
import Link from 'next/link';

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function History() {
  const [year, setYear] = useState('');
  const [kind, setKind] = useState('');
  const [search, setSearch] = useState('');
  const [desc, setDesc] = useState(true);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const { isOpen, onOpen, onClose } = useDisclosure();

  const params = new URLSearchParams();
  if (year) params.append('year', year);
  if (kind) params.append('kind', kind);
  const { data, mutate } = useSWR(`/api/payslip/list?${params.toString()}`, fetcher);

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.toLowerCase();
    const arr = data.filter((p: any) => {
      if (!q) return true;
      return (
        (p.date && p.date.includes(q)) ||
        (p.filename && p.filename.toLowerCase().includes(q)) ||
        String(p.net_amount || '').includes(q) ||
        String(p.gross_amount || '').includes(q)
      );
    });
    arr.sort((a: any, b: any) => {
      const aDate = a.date ? new Date(a.date).getTime() : 0;
      const bDate = b.date ? new Date(b.date).getTime() : 0;
      return desc ? bDate - aDate : aDate - bDate;
    });
    return arr;
  }, [data, search, desc]);

  const askDelete = (id: number) => {
    setDeleteId(id);
    onOpen();
  };

  const confirmDelete = async () => {
    if (deleteId == null) return;
    await fetch(`/api/payslip/delete?payslip_id=${deleteId}`, { method: 'DELETE' });
    setDeleteId(null);
    onClose();
    mutate();
  };

  return (
    <Layout>
      <Stack spacing={4}>
        <Heading as="h1" size="lg">明細一覧</Heading>
        <Stack direction={{ base: 'column', md: 'row' }} spacing={2}>
          <Select placeholder="年" value={year} onChange={e => setYear(e.target.value)} maxW="100px">
            <option value="2023">2023</option>
            <option value="2024">2024</option>
            <option value="2025">2025</option>
          </Select>
          <Select placeholder="種別" value={kind} onChange={e => setKind(e.target.value)} maxW="120px">
            <option value="salary">給与</option>
            <option value="bonus">賞与</option>
          </Select>
          <Input placeholder="検索" value={search} onChange={e => setSearch(e.target.value)} maxW="200px" />
          <Button onClick={() => setDesc(!desc)}>並び替え</Button>
        </Stack>
        <Table size="sm">
          <Thead>
            <Tr>
              <Th>年月</Th>
              <Th>種別</Th>
              <Th isNumeric>額面</Th>
              <Th isNumeric>手取り</Th>
              <Th isNumeric>控除</Th>
              <Th>操作</Th>
            </Tr>
          </Thead>
          <Tbody>
            {filtered.map((p: any) => (
              <Tr key={p.id}>
                <Td>{p.date || '-'}</Td>
                <Td>
                  <Tag colorScheme={p.type === 'bonus' ? 'pink' : 'teal'}>{p.type || '-'}</Tag>
                </Td>
                <Td isNumeric>{p.gross_amount?.toLocaleString()}</Td>
                <Td isNumeric>{p.net_amount?.toLocaleString()}</Td>
                <Td isNumeric>{p.deduction_amount?.toLocaleString()}</Td>
                <Td>
                  <Stack direction="row" spacing={1}>
                    <IconButton as={Link} href={`/payslip/${p.id}`} aria-label="detail" icon={<ViewIcon />} size="sm" />
                    <IconButton as={Link} href={`/payslip/${p.id}?edit=1`} aria-label="edit" icon={<EditIcon />} size="sm" />
                    <IconButton onClick={() => askDelete(p.id)} aria-label="delete" icon={<DeleteIcon />} size="sm" />
                    <IconButton as={Link} href={`/upload?copy=${p.id}`} aria-label="copy" icon={<CopyIcon />} size="sm" />
                  </Stack>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Stack>

      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>削除確認</ModalHeader>
          <ModalBody>本当に削除しますか？</ModalBody>
          <ModalFooter>
            <Button mr={3} onClick={onClose}>キャンセル</Button>
            <Button colorScheme="red" onClick={confirmDelete}>削除</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Layout>
  );
}
