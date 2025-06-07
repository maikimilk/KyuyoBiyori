import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import useSWR from 'swr';
import { useMemo, useState } from 'react';
import {
  Heading,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Select,
  Flex,
  Box,
  Input,
  Switch,
  FormControl,
  FormLabel,
} from '@chakra-ui/react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line, Bar, Pie } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
);

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function Visualize() {
  const router = useRouter();
  const thisYear = new Date().getFullYear();
  const [period, setPeriod] = useState('this');
  const [color, setColor] = useState('#3182ce');
  const [showLabel, setShowLabel] = useState(true);

  const yearParam = useMemo(() => {
    if (period === 'this') return thisYear;
    if (period === 'last') return thisYear - 1;
    return undefined;
  }, [period, thisYear]);

  const statsQuery = (target: string, kind?: string) => {
    const params = new URLSearchParams();
    params.append('period', kind === 'bonus' ? 'yearly' : 'monthly');
    params.append('target', target);
    if (kind) params.append('kind', kind);
    if (yearParam) params.append('year', String(yearParam));
    return `/api/payslip/stats?${params.toString()}`;
  };

  const { data: net } = useSWR(statsQuery('net'), fetcher);
  const { data: gross } = useSWR(statsQuery('gross'), fetcher);
  const { data: bonus } = useSWR(statsQuery('net', 'bonus'), fetcher);
  const { data: deduction } = useSWR(
    yearParam ? `/api/payslip/breakdown?year=${yearParam}&category=deduction` : null,
    fetcher,
  );

  const netData = useMemo(
    () => ({
      labels: net?.labels || [],
      datasets: [
        {
          label: '手取り',
          data: net?.data || [],
          backgroundColor: color,
          borderColor: color,
        },
      ],
    }),
    [net, color],
  );

  const grossData = useMemo(
    () => ({
      labels: gross?.labels || [],
      datasets: [
        {
          label: '額面',
          data: gross?.data || [],
          backgroundColor: color,
          borderColor: color,
        },
      ],
    }),
    [gross, color],
  );

  const bonusData = useMemo(
    () => ({
      labels: bonus?.labels || [],
      datasets: [
        {
          label: '賞与',
          data: bonus?.data || [],
          backgroundColor: color,
        },
      ],
    }),
    [bonus, color],
  );

  const breakdownData = useMemo(
    () => ({
      labels: deduction?.labels || [],
      datasets: [
        {
          label: '控除',
          data: deduction?.data || [],
          backgroundColor: (deduction?.labels || []).map(() => color),
        },
      ],
    }),
    [deduction, color],
  );

  const onChartClick = (labels: string[]) => (event: any, elements: any[]) => {
    if (!elements.length) return;
    const idx = elements[0].index;
    const label = labels[idx];
    if (label) router.push(`/history?search=${label}`);
  };

  return (
    <Layout>
      <Heading as="h1" size="lg" mb={4}>
        グラフ分析
      </Heading>
      <Flex mb={4} gap={4} align="center" wrap="wrap">
        <Select value={period} onChange={e => setPeriod(e.target.value)} maxW="120px">
          <option value="this">今年</option>
          <option value="last">昨年</option>
          <option value="all">全期間</option>
        </Select>
        <FormControl display="flex" alignItems="center" width="auto">
          <FormLabel htmlFor="show" mb="0">
            ラベル
          </FormLabel>
          <Switch id="show" isChecked={showLabel} onChange={e => setShowLabel(e.target.checked)} />
        </FormControl>
        <Input type="color" value={color} onChange={e => setColor(e.target.value)} width="60px" p={1} />
      </Flex>
      <Tabs variant="enclosed">
        <TabList>
          <Tab>手取り推移</Tab>
          <Tab>額面推移</Tab>
          <Tab>控除内訳</Tab>
          <Tab>賞与比較</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            <Line
              options={{ plugins: { legend: { display: showLabel } } }}
              data={netData}
              onClick={onChartClick(netData.labels)}
            />
          </TabPanel>
          <TabPanel>
            <Line
              options={{ plugins: { legend: { display: showLabel } } }}
              data={grossData}
              onClick={onChartClick(grossData.labels)}
            />
          </TabPanel>
          <TabPanel>
            {deduction ? (
              <Pie
                options={{ plugins: { legend: { display: showLabel } } }}
                data={breakdownData}
                onClick={onChartClick(breakdownData.labels)}
              />
            ) : (
              <Box>データなし</Box>
            )}
          </TabPanel>
          <TabPanel>
            <Bar
              options={{ plugins: { legend: { display: showLabel } } }}
              data={bonusData}
              onClick={onChartClick(bonusData.labels)}
            />
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Layout>
  );
}
