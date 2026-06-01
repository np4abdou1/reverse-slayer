'use client';
import Link from 'next/link';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
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
      <h1 style={{ fontSize: '4rem', fontWeight: '900', color: '#fff', marginBottom: '20px' }}>Oops!</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: '18px', marginBottom: '30px' }}>
        Something went wrong while loading this page.
      </p>
      <div style={{ display: 'flex', gap: '15px' }}>
        <button
          onClick={() => reset()}
          style={{
            padding: '12px 24px',
            backgroundColor: 'var(--primary)',
            color: '#000',
            border: 'none',
            borderRadius: '8px',
            fontWeight: 'bold',
            cursor: 'pointer'
          }}
        >
          Try Again
        </button>
        <Link
          href="/"
          style={{
            padding: '12px 24px',
            backgroundColor: 'rgba(255,255,255,0.05)',
            color: '#fff',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '8px',
            fontWeight: 'bold'
          }}
        >
          Go Home
        </Link>
      </div>
    </div>
  );
}
