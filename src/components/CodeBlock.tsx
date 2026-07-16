import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, Copy, Download } from 'lucide-react';
import RevealOnView from './motion/RevealOnView';

interface Props {
  code: string;
  language?: string;
  filename?: string;
}

const EXTENSIONS: Record<string, string> = {
  bash: 'sh',
  sh: 'sh',
  shell: 'sh',
  python: 'py',
  sql: 'sql',
  hcl: 'tf',
  terraform: 'tf',
  yaml: 'yaml',
  yml: 'yaml',
  json: 'json',
  javascript: 'js',
  typescript: 'ts',
};

function downloadFilename(language: string, filename?: string): string {
  if (filename) return filename;
  const ext = EXTENSIONS[language] ?? 'txt';
  return `snippet.${ext}`;
}

export default function CodeBlock({ code, language = 'bash', filename }: Props) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const download = () => {
    const blob = new Blob([code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = downloadFilename(language, filename);
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <RevealOnView className="my-6 overflow-hidden rounded-xl border border-[var(--border)] bg-[#0f172a]">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-slate-400">{language}</span>
          {filename && <span className="text-xs text-slate-500">{filename}</span>}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={download}
            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            aria-label={`Download ${downloadFilename(language, filename)}`}
            title={`Download ${downloadFilename(language, filename)}`}
          >
            <Download className="h-3.5 w-3.5" />
            Download
          </button>
          <button
            onClick={copy}
            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            aria-label="Copy code"
          >
            <AnimatePresence mode="wait" initial={false}>
              {copied ? (
                <motion.span
                  key="copied"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ duration: 0.12 }}
                  className="flex items-center gap-1.5"
                >
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </motion.span>
              ) : (
                <motion.span
                  key="copy"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ duration: 0.12 }}
                  className="flex items-center gap-1.5"
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy
                </motion.span>
              )}
            </AnimatePresence>
          </button>
        </div>
      </div>
      <pre className="m-0 overflow-x-auto p-4 text-sm leading-relaxed">
        <code className={`language-${language}`}>{code}</code>
      </pre>
    </RevealOnView>
  );
}
