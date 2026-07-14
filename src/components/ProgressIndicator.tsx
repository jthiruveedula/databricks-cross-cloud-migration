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
    <div className="fixed left-0 top-[var(--header-height)] z-50 h-0.5 w-full bg-[var(--border)]">
      <div
        className="h-full bg-gradient-to-r from-[var(--accent)] to-violet-500 transition-all"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
