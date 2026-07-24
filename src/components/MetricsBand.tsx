import React, { useEffect, useRef, useState } from 'react';
import { motion, useInView } from 'framer-motion';
import { Cloud, Route, CalendarClock, BookText } from 'lucide-react';

interface Metric {
  value: number;
  suffix?: string;
  label: string;
  icon: React.ElementType;
  decimals?: number;
}

const METRICS: Metric[] = [
  { value: 3, suffix: '', label: 'Clouds supported', icon: Cloud },
  { value: 7, suffix: '', label: 'Migration phases', icon: Route },
  { value: 6, suffix: '–30+', label: 'Weeks, depending on scope & tooling', icon: CalendarClock },
  { value: 100, suffix: '+', label: 'Runbook pages', icon: BookText },
];

function useCountUp(target: number, active: boolean, decimals = 0) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!active) return;
    let raf = 0;
    const start = performance.now();
    const duration = 1400;
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Number((target * eased).toFixed(decimals)));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, active, decimals]);
  return value;
}

function MetricCard({ metric, active }: { metric: Metric; active: boolean }) {
  const value = useCountUp(metric.value, active, metric.decimals ?? 0);
  const display = metric.decimals ? value.toFixed(metric.decimals) : Math.round(value).toString();
  return (
    <div className="relative overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 text-center">
      <div className="absolute inset-0 bg-gradient-to-br from-[var(--accent)]/5 via-transparent to-transparent opacity-0 transition-opacity duration-500 hover:opacity-100" />
      <metric.icon className="relative mx-auto mb-3 h-6 w-6 text-[var(--accent)]" />
      <div className="relative text-4xl font-bold tracking-tight text-[var(--ink)]">
        {display}
        {metric.suffix && <span className="text-[var(--accent)]">{metric.suffix}</span>}
      </div>
      <div className="relative mt-1 text-sm text-[var(--ink-muted)]">{metric.label}</div>
    </div>
  );
}

export default function MetricsBand() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <div ref={ref} className="my-12 grid grid-cols-2 gap-4 lg:grid-cols-4">
      {METRICS.map((m, i) => (
        <motion.div
          key={m.label}
          initial={{ opacity: 0, y: 16 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: i * 0.08, ease: 'easeOut' }}
        >
          <MetricCard metric={m} active={inView} />
        </motion.div>
      ))}
    </div>
  );
}
