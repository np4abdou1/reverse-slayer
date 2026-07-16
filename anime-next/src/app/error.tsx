'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [countdown, setCountdown] = useState(0);
  const isDev = process.env.NODE_ENV === 'development';

  useEffect(() => {
    console.error('Page error:', error);
  }, [error]);

  const handleAutoRetry = () => {
    setCountdown(5);
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          reset();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const isNetwork = error.message?.includes('fetch') || error.message?.includes('network');
  const is404 = error.message?.includes('404') || error.digest?.includes('404');

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center gap-4 px-4">
      <h1 className="text-6xl md:text-8xl font-black text-border tracking-tighter">
        {is404 ? '404' : 'خطأ'}
      </h1>
      <p className="text-muted-fg text-sm max-w-md leading-relaxed">
        {isNetwork
          ? 'تعذر الاتصال بالخادم. يرجى التحقق من اتصالك بالإنترنت.'
          : is404
          ? 'الصفحة التي تبحث عنها غير موجودة.'
          : 'حدث خطأ أثناء تحميل هذه الصفحة. الرجاء المحاولة مرة أخرى.'}
      </p>
      {isDev && error.message && (
        <p className="text-xs text-red-400/60 max-w-lg font-mono bg-red-950/20 p-3 rounded border border-red-900/30">
          {error.message}
        </p>
      )}
      <div className="flex gap-3 mt-4 flex-wrap justify-center">
        <button
          onClick={countdown > 0 ? undefined : handleAutoRetry}
          disabled={countdown > 0}
          className="bg-foreground text-background px-6 py-2.5 text-sm font-bold uppercase tracking-widest hover:bg-transparent hover:text-foreground hover:border hover:border-foreground transition-all disabled:opacity-50"
        >
          {countdown > 0 ? `إعادة تلقائياً (${countdown})` : 'إعادة المحاولة'}
        </button>
        <Link
          href="/"
          className="border border-border px-6 py-2.5 text-sm font-bold uppercase tracking-widest text-muted-fg hover:text-foreground hover:border-foreground transition-all"
        >
          الرئيسية
        </Link>
      </div>
    </div>
  );
}
