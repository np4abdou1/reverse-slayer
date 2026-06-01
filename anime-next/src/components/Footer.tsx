import Link from 'next/link';

export default function Footer() {
  return (
    <footer style={{
      padding: '32px 0 24px',
      borderTop: '1px solid var(--border)',
      color: 'var(--text-muted)',
      fontSize: '12px'
    }}>
      <div className="container">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ fontWeight: '700', color: 'var(--foreground)' }}>
            Anime<span style={{ color: '#999' }}>Slayer</span>
          </div>
          <div style={{ display: 'flex', gap: '16px' }}>
            <Link href="/">Home</Link>
            <Link href="/?type=currently_airing">Trending</Link>
            <Link href="/?type=top_anime">Top Rated</Link>
          </div>
          <div style={{ opacity: 0.5 }}>
            &copy; {new Date().getFullYear()} Anime Slayer
          </div>
        </div>
      </div>
    </footer>
  );
}
