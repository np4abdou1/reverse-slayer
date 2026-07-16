interface PageHeaderProps {
  title: string;
  subtitle?: string;
  meta?: string;
  page?: number;
}

export default function PageHeader({ title, subtitle, meta, page }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-baseline gap-3 border-b border-border pb-3 mb-5" dir="rtl">
      <h1 className="text-xl md:text-2xl font-black tracking-tight text-foreground">
        {title}
      </h1>
      {subtitle && (
        <span className="text-xs text-muted font-bold opacity-80">{subtitle}</span>
      )}
      {meta && (
        <span className="text-[10px] text-muted-fg tracking-widest font-black uppercase bg-foreground/10 px-2 py-0.5 rounded-sm">{meta}</span>
      )}
    </div>
  );
}
