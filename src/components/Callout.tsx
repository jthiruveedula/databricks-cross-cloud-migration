import React from 'react';
import { motion } from 'framer-motion';
import { Info, AlertTriangle, CheckCircle, Lightbulb, ShieldAlert } from 'lucide-react';
import RevealOnView from './motion/RevealOnView';

type Variant = 'note' | 'warning' | 'tip' | 'prerequisite' | 'decision';

const icons: Record<Variant, React.ElementType> = {
  note: Info,
  warning: AlertTriangle,
  tip: Lightbulb,
  prerequisite: ShieldAlert,
  decision: CheckCircle,
};

const styles: Record<Variant, string> = {
  note: 'border-l-blue-500 bg-blue-500/5 hover:bg-blue-500/10 text-blue-900 dark:text-blue-100',
  warning: 'border-l-amber-500 bg-amber-500/5 hover:bg-amber-500/10 text-amber-900 dark:text-amber-100',
  tip: 'border-l-emerald-500 bg-emerald-500/5 hover:bg-emerald-500/10 text-emerald-900 dark:text-emerald-100',
  prerequisite: 'border-l-violet-500 bg-violet-500/5 hover:bg-violet-500/10 text-violet-900 dark:text-violet-100',
  decision: 'border-l-sky-500 bg-sky-500/5 hover:bg-sky-500/10 text-sky-900 dark:text-sky-100',
};

interface Props {
  variant?: Variant;
  title?: string;
  children: React.ReactNode;
}

export default function Callout({ variant = 'note', title, children }: Props) {
  const Icon = icons[variant];
  const label = title ?? variant.charAt(0).toUpperCase() + variant.slice(1);
  const shouldPulse = variant === 'warning' || variant === 'prerequisite';
  return (
    <RevealOnView x={-12} y={0} className={`my-6 rounded-r-lg border-l-4 p-4 transition-colors duration-200 ${styles[variant]}`}>
      <div className="mb-2 flex items-center gap-2 font-semibold">
        {shouldPulse ? (
          <motion.span
            animate={{ scale: [1, 1.15, 1] }}
            transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
            className="flex items-center"
          >
            <Icon className="h-4 w-4" />
          </motion.span>
        ) : (
          <Icon className="h-4 w-4" />
        )}
        <span>{label}</span>
      </div>
      <div className="text-sm leading-relaxed opacity-90">{children}</div>
    </RevealOnView>
  );
}
