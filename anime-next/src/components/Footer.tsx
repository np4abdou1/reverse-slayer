import Link from 'next/link';
import Container from './Container';

export default function Footer() {
  return (
    <footer className="border-t border-border mt-auto py-8 bg-card">
      <Container>
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="font-black text-2xl tracking-tighter text-foreground opacity-50">
              ANIME<span className="font-normal">BIND</span>
            </span>
          </div>
          <div className="flex gap-6 text-sm font-bold tracking-wide">
            <Link href="/dmca" className="text-muted hover:text-foreground transition-colors">DMCA</Link>
            <Link href="/contact-us" className="text-muted hover:text-foreground transition-colors">اتصل بنا</Link>
          </div>
        </div>
      </Container>
    </footer>
  );
}
