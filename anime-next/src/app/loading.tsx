export default function Loading() {
  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'var(--background)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 2000
    }}>
      <div 
        className="animate-spin"
        style={{
          width: '40px',
          height: '40px',
          border: '3px solid rgba(255,255,255,0.1)',
          borderTopColor: 'var(--primary)',
          borderRadius: '50%',
        }} 
      />
      <p style={{ marginTop: '20px', color: 'var(--text-muted)', fontSize: '14px', fontWeight: '600', letterSpacing: '1px' }}>
        LOADING...
      </p>
    </div>
  );
}
