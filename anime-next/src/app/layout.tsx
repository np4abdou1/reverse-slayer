import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
});

export const metadata: Metadata = {
  title: {
    default: "Anime Slayer | Watch Anime Online in HD",
    template: "%s | Anime Slayer"
  },
  description: "Experience anime like never before with our high-speed, professional streaming interface. Watch the latest episodes and discover top-rated series.",
  keywords: ["anime", "streaming", "anime slayer", "watch anime", "hd anime"],
  authors: [{ name: "Anime Slayer Team" }],
  robots: "index, follow",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${outfit.variable}`}>
        <Header />
        <main style={{ minHeight: 'calc(100vh - 200px)' }}>
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
