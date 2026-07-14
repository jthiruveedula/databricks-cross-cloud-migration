import React from 'react';
import { Cloud, Database, RefreshCw, Share2, Terminal, Box } from 'lucide-react';

interface ToolDef {
  icon: React.ElementType;
  bg: string;
  text: string;
}

const TOOLS: Record<string, ToolDef> = {
  'Databricks CLI': { icon: Terminal, bg: 'bg-rose-600', text: 'text-white' },
  'UCX': { icon: Database, bg: 'bg-teal-600', text: 'text-white' },
  'Terraform provider': { icon: Box, bg: 'bg-violet-600', text: 'text-white' },
  'Delta Deep Clone': { icon: RefreshCw, bg: 'bg-blue-600', text: 'text-white' },
  'Cloud CLIs': { icon: Cloud, bg: 'bg-amber-600', text: 'text-white' },
  'Delta Sharing': { icon: Share2, bg: 'bg-cyan-600', text: 'text-white' },
};

export default function ToolLogo({ name, className = '' }: { name: string; className?: string }) {
  const tool = TOOLS[name] ?? { icon: Box, bg: 'bg-slate-500', text: 'text-white' };
  const Icon = tool.icon;
  return (
    <span
      className={`inline-flex h-10 w-10 items-center justify-center rounded-xl shadow-sm ${tool.bg} ${tool.text} ${className}`}
      aria-label={name}
    >
      <Icon className="h-5 w-5" />
    </span>
  );
}
