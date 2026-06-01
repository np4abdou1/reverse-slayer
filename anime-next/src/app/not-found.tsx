import Link from 'next/link';

export default function NotFound() {
  return (
    <div style={{
      height: 'calc(100vh - 200px)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      textAlign: 'center',
      padding: '20px'
    }}>
      <h1 style={{ fontSize: '6rem', fontWeight: '900', color: 'var(--primary)', marginBottom: '10px' }}>404</h1>
      <h2 style={{ fontSize: '2rem', color: '#fff', marginBottom: '20px' }}>Page Not Found</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: '18px', marginBottom: '30px', maxWidth: '500px' }}>
        The anime episode or page you are looking for doesn't exist or has been moved.
      </p>
      <Link
        href="/"
        style={{
          padding: '12px 30px',
          backgroundColor: 'var(--primary)',
          color: '#000',
          border: 'none',
          borderRadius: '12px',
          fontWeight: '800',
          fontSize: '16px',
          transition: 'transform 0.2s'
        }}
      >
        Return to Home
      </Link>
    </div>
  );
}
