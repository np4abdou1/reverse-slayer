import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center gap-4">
      <h1 className="text-7xl md:text-9xl font-black text-border tracking-tighter">404</h1>
      <h2 className="text-xl md:text-2xl font-black text-foreground">الصفحة غير موجودة</h2>
      <p className="text-muted text-sm max-w-md">
        الصفحة أو الأنمي الذي تبحث عنه غير موجود أو تم نقله.
      </p>
      <Link
        href="/"
        className="mt-4 inline-flex items-center gap-2 px-8 py-3 bg-foreground text-background font-bold text-sm uppercase tracking-widest hover:bg-transparent hover:text-foreground hover:border hover:border-foreground transition-all"
      >
        العودة للرئيسية
      </Link>
    </div>
  );
}
