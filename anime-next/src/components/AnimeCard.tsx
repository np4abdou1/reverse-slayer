'use client';
import Image from 'next/image';
import Link from 'next/link';
import { Star, Tv, Film, Clapperboard } from 'lucide-react';
import { useState } from 'react';

interface AnimeCardProps {
  id: string;
  name: string;
  image: string;
  rating: string | null;
  type: string;
  year: string;
}

const typeIcon: Record<string, React.ReactNode> = {
  movie: <Film size={10} />,
  tv: <Tv size={10} />,
};

export default function AnimeCard({ id, name, image, rating, type, year }: AnimeCardProps) {
  const [imgError, setImgError] = useState(false);

  return (
    <Link href={`/anime/${id}`} className="anime-card">
      <div style={{ position: 'relative', aspectRatio: '3/4', width: '100%', backgroundColor: '#e8e8ed' }}>
        {!imgError ? (
          <Image
            src={image}
            alt={name}
            fill
            sizes="(max-width: 768px) 50vw, (max-width: 1200px) 25vw, 20vw"
            style={{ objectFit: 'cover' }}
            loading="lazy"
            unoptimized
            onError={() => setImgError(true)}
          />
        ) : (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: '#fff', fontSize: '12px', fontWeight: '600', padding: '20px', textAlign: 'center', backgroundColor: '#1a1a1a'
          }}>
            {name}
          </div>
        )}
        <div style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, transparent 55%)',
        }} />

        {rating && (
          <div style={{
            position: 'absolute', top: '8px', right: '8px',
            backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
            padding: '3px 7px', borderRadius: '5px',
            display: 'flex', alignItems: 'center', gap: '3px',
            fontSize: '10px', fontWeight: '700', color: '#fff',
          }}>
            <Star size={9} fill="#ffd43b" color="#ffd43b" />
            {rating}
          </div>
        )}

        <div style={{
          position: 'absolute', bottom: '10px', left: '10px', right: '10px',
        }}>
          <h3 style={{
            fontSize: '12px', fontWeight: '700', color: '#fff',
            marginBottom: '3px',
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
            overflow: 'hidden', lineHeight: '1.3'
          }}>
            {name}
          </h3>
          <div style={{ display: 'flex', gap: '6px', fontSize: '9px', color: 'rgba(255,255,255,0.6)', fontWeight: '600', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>{typeIcon[type] || <Clapperboard size={9} />}{type}</span>
            {year && <><span>•</span><span>{year}</span></>}
          </div>
        </div>
      </div>
    </Link>
  );
}
