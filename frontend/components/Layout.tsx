import Link from 'next/link';
import { ReactNode } from 'react';
import { Box, Flex, Link as ChakraLink } from '@chakra-ui/react';

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <Box>
      <Flex as="nav" p={4} borderBottom="1px" borderColor="gray.200" gap={4}>
        <ChakraLink as={Link} href="/">ホーム</ChakraLink>
        <ChakraLink as={Link} href="/upload">アップロード</ChakraLink>
        <ChakraLink as={Link} href="/history">明細一覧</ChakraLink>
        <ChakraLink as={Link} href="/visualize">グラフ分析</ChakraLink>
        <ChakraLink as={Link} href="/settings">設定</ChakraLink>
      </Flex>
      <Box p={4}>{children}</Box>
    </Box>
  );
}
