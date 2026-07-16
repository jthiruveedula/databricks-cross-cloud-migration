import React, { useEffect, useState } from 'react';

export default function ProgressIndicator() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const scroll = window.scrollY;
      setProgress(docHeight > 0 ? (scroll / docHeight) * 100 : 0);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div
      className="fixed left-0 top-[var(--header-height)] z-50 h-0.5 w-full bg-[var(--border)]"
      role="progressbar"
      aria-valuenow={Math.round(progress)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full rounded-r-full bg-gradient-to-r from-[var(--accent)] to-orange-400 transition-all duration-150 ease-out"
        style={{
          width: `${progress}%`,
          boxShadow: progress > 0 ? '0 0 8px var(--glow-color)' : 'none',
        }}
      />
    </div>
  );
}
