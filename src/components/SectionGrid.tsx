import { motion, useReducedMotion } from 'framer-motion';
import {
  BookOpen, Cloud, Shield, Cpu, Workflow, ClipboardList, Activity, Wrench,
  Zap, BarChart3, Brain, Lock, FileText, Share2, AlertTriangle,
} from 'lucide-react';
import Card from './Card';
import { withBase } from '../lib/paths';

// A client:visible island can't accept a React component reference (a function) as a
// prop -- Astro's hydration serializer only round-trips JSON-safe data, so passing the
// lucide icon component directly renders an empty island with no error. Pass the icon's
// name instead and resolve it in this same client-side module, where the function
// reference never needs to cross the server/client boundary.
const ICONS: Record<string, React.ElementType> = {
  BookOpen, Cloud, Shield, Cpu, Workflow, ClipboardList, Activity, Wrench,
  Zap, BarChart3, Brain, Lock, FileText, Share2, AlertTriangle,
};

export interface SectionItem {
  title: string;
  description: string;
  href: string;
  icon: keyof typeof ICONS;
}

interface Props {
  sections: SectionItem[];
  columns?: string;
}

const container = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
};

const item = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
};

// Animate Card directly, not a div wrapped around it -- see the comment on Card's
// forwardRef for why a separate wrapper caused a CSS Grid row-height mismatch.
const MotionCard = motion(Card);

/**
 * Staggered scroll-reveal grid for the landing page's section cards. framer-motion's
 * variant propagation (parent staggerChildren -> child variants) does the stagger;
 * RevealOnView (used elsewhere for single content blocks) doesn't cover a per-item
 * map, so this is a small sibling rather than a misfit reuse.
 */
export default function SectionGrid({ sections, columns = 'sm:grid-cols-2 lg:grid-cols-4' }: Props) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      className={`grid gap-6 ${columns}`}
      initial={reduceMotion ? false : 'hidden'}
      whileInView="visible"
      viewport={{ once: true, margin: '-60px' }}
      variants={reduceMotion ? undefined : container}
    >
      {sections.map((s) => (
        <MotionCard
          key={s.title}
          variants={reduceMotion ? undefined : item}
          href={withBase(s.href)}
          title={s.title}
          description={s.description}
          icon={ICONS[s.icon]}
        />
      ))}
    </motion.div>
  );
}
