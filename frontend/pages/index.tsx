import React, { useState } from 'react';
import useSWR from 'swr';
import Layout from '../components/Layout';
import { Heading, Stack, Stat, StatLabel, StatNumber, Tabs, TabList, TabPanels, Tab, TabPanel, ButtonGroup, Button, Text } from '@chakra-ui/react';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function Home() {
  const { data: summary } = useSWR('/api/payslip/summary', fetcher);
  const [target, setTarget] = useState<'net' | 'gross' | 'deduction'>('net');
  const [period, setPeriod] = useState<'monthly' | 'yearly'>('monthly');
  const { data: stats } = useSWR(`/api/payslip/stats?target=${target}&period=${period}`, fetcher);

  const hasData = !!(stats && stats.labels && stats.labels.length > 0);
  const chartData = {
    labels: stats?.labels || [],
    datasets: [
      {
        label: target,
        data: stats?.data || [],
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75,192,192,0.2)',
      },
    ],
  };

  return (
    <Layout>
      <Stack spacing={6}>
        <Heading as="h1" size="lg">ダッシュボード</Heading>
        <Stack direction={{ base: 'column', md: 'row' }} spacing={4}>
          <Stat>
            <StatLabel>今月手取り</StatLabel>
            <StatNumber>{summary ? summary.net_this_month : '--'}円</StatNumber>
          </Stat>
          <Stat>
            <StatLabel>今月額面</StatLabel>
            <StatNumber>{summary ? summary.gross_this_month : '--'}円</StatNumber>
          </Stat>
          <Stat>
            <StatLabel>今月控除</StatLabel>
            <StatNumber>{summary ? summary.deduction_this_month ?? 0 : '--'}円</StatNumber>
          </Stat>
          <Stat>
            <StatLabel>賞与累計</StatLabel>
            <StatNumber>{summary ? summary.bonus_total : '--'}円</StatNumber>
          </Stat>
          <Stat>
            <StatLabel>前月比</StatLabel>
            <StatNumber>{summary ? summary.diff_vs_prev_month : '--'}円</StatNumber>
          </Stat>
        </Stack>
        {hasData ? (
          <React.Fragment>
            <ButtonGroup size="sm" isAttached>
              <Button variant={period === 'monthly' ? 'solid' : 'outline'} onClick={() => setPeriod('monthly')}>月次</Button>
              <Button variant={period === 'yearly' ? 'solid' : 'outline'} onClick={() => setPeriod('yearly')}>年次</Button>
            </ButtonGroup>
            <Tabs index={['net','gross','deduction'].indexOf(target)} onChange={(i) => setTarget(['net','gross','deduction'][i] as 'net' | 'gross' | 'deduction')}>
              <TabList>
                <Tab>手取り</Tab>
                <Tab>額面</Tab>
                <Tab>控除</Tab>
              </TabList>
              <TabPanels>
                <TabPanel><Line data={chartData} /></TabPanel>
                <TabPanel><Line data={chartData} /></TabPanel>
                <TabPanel><Line data={chartData} /></TabPanel>
              </TabPanels>
            </Tabs>
          </React.Fragment>
        ) : (
          <Text color="gray.500">アップロードしてはじめよう！</Text>
        )
        }
      </Stack>
    </Layout>
  );
}
