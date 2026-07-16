import type { Metadata, Viewport } from 'next';
import { Cairo, Inter } from 'next/font/google';
import './globals.css';
import Header from '@/components/Header';
import Footer from '@/components/Footer';

const cairo = Cairo({
  subsets: ['arabic', 'latin'],
  weight: ['200', '300', '400', '500', '600', '700', '800', '900', '1000'],
  variable: '--font-cairo',
  display: 'swap',
});

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  themeColor: '#000000',
};

export const metadata: Metadata = {
  title: 'AnimeBind | انمي بايند',
  description: 'AnimeBind - موقع لمشاهدة وتحميل الانمي المترجم بجودة عالية اونلاين. شاهد افضل مسلسلات وافلام واوفا الانمي مترجمة للعربية.',
  openGraph: {
    title: 'AnimeBind | انمي بايند',
    description: 'AnimeBind - موقع لمشاهدة وتحميل الانمي المترجم بجودة عالية اونلاين.',
    type: 'website',
    siteName: 'AnimeBind',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'AnimeBind | انمي بايند',
    description: 'شاهد الانمي المترجم بجودة عالية اونلاين',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl" className={`${cairo.variable} ${inter.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{
          __html: `
            (function() {
              try {
                var theme = localStorage.getItem('theme');
                if (theme === 'light') {
                  document.documentElement.classList.add('light');
                }
              } catch(e) {}
            })();
          `
        }} />
      </head>
      <body className="antialiased min-h-screen flex flex-col font-sans bg-background text-foreground">
        <Header />
        <main className="flex-1 w-full animate-fade-in">
          <div className="w-full max-w-6xl mx-auto px-4 md:px-6 pt-8 pb-20">
            {children}
          </div>
          <Footer />
        </main>
      </body>
    </html>
  );
}
