import { AppProps } from 'next/app';
import { ChakraProvider, ColorModeScript } from '@chakra-ui/react';
import { useEffect } from 'react';

export default function MyApp({ Component, pageProps }: AppProps) {
  useEffect(() => {
    const stored = localStorage.getItem('settings');
    if (stored) {
      const { color } = JSON.parse(stored);
      if (color) {
        document.documentElement.style.setProperty('--chakra-colors-teal-500', color);
      }
    }
  }, []);
  return (
    <ChakraProvider>
      <ColorModeScript />
      <Component {...pageProps} />
    </ChakraProvider>
  );
}
