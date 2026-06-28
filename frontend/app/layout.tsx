import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import '../styles/globals.css';

const inter = Inter({
  subsets: ['latin', 'cyrillic'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Best Price — Сравнение цен в реальном времени',
  description: 'Ищите товары и сравнивайте цены из 6 магазинов: Onliner.by, Wildberries, Ozon, Shop.by, 1k.by, 360shop.by.',
  keywords: ['Best Price', 'сравнение цен', 'поиск товаров', 'цены', 'онлайн-покупки'],
  authors: [{ name: 'Best Price Team' }],
  creator: 'Best Price Team',
  icons: {
    icon: [
      {
        url: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="%233b82f6"/><text x="16" y="22" text-anchor="middle" font-family="system-ui" font-weight="800" font-size="18" fill="white">B</text></svg>',
        type: 'image/svg+xml',
      },
    ],
  },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    siteName: 'Best Price',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Best Price — Сравнение цен',
    description: 'Ищите товары и сравнивайте цены из 6 магазинов.',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className={`${inter.variable}`} suppressHydrationWarning>
      <body className="font-sans antialiased min-h-screen bg-[#f5f6fa] text-slate-900">
        {children}
      </body>
    </html>
  );
}
