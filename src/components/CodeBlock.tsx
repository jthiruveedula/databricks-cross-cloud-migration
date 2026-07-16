import React, { useCallback, useState } from 'react';
import { Highlight, themes } from 'prism-react-renderer';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, Copy, Download, WrapText, FileCode2 } from 'lucide-react';
import RevealOnView from './motion/RevealOnView';

interface Props {
  code: string;
  language?: string;
  filename?: string;
  highlight?: number[];
  showLineNumbers?: boolean;
  wrap?: boolean;
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

const LANG_LABELS: Record<string, string> = {
  bash: 'Bash',
  sh: 'Bash',
  shell: 'Bash',
  python: 'Python',
  sql: 'SQL',
  hcl: 'Terraform',
  terraform: 'Terraform',
  yaml: 'YAML',
  yml: 'YAML',
  json: 'JSON',
  javascript: 'JavaScript',
  typescript: 'TypeScript',
  js: 'JavaScript',
  ts: 'TypeScript',
  py: 'Python',
};

function downloadFilename(language: string, filename?: string): string {
  if (filename) return filename;
  const ext = EXTENSIONS[language] ?? 'txt';
  return `snippet.${ext}`;
}

export default function CodeBlock({
  code,
  language = 'bash',
  filename,
  highlight = [],
  showLineNumbers = true,
  wrap = false,
}: Props) {
  const [copied, setCopied] = useState(false);
  const [wrapEnabled, setWrapEnabled] = useState(wrap);
  const [copiedLine, setCopiedLine] = useState<number | null>(null);

  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const copyLine = useCallback(async (lineText: string, lineNum: number) => {
    await navigator.clipboard.writeText(lineText);
    setCopiedLine(lineNum);
    setTimeout(() => setCopiedLine(null), 1500);
  }, []);

  const download = () => {
    const blob = new Blob([code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = downloadFilename(language, filename);
    a.click();
    URL.revokeObjectURL(url);
  };

  const lineCount = code.split('\n').length;
  const label = LANG_LABELS[language] || language.toUpperCase();

  return (
    <RevealOnView className="my-6 overflow-hidden rounded-xl border border-[var(--border)] shadow-lg">
      {/* Title bar — VS Code style */}
      <div className="flex items-center justify-between border-b border-white/10 bg-[#1e293b] px-4 py-2">
        <div className="flex items-center gap-3">
          {/* Traffic light dots */}
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-red-500/80 transition-transform hover:scale-125" />
            <span className="h-3 w-3 rounded-full bg-yellow-500/80 transition-transform hover:scale-125" />
            <span className="h-3 w-3 rounded-full bg-green-500/80 transition-transform hover:scale-125" />
          </div>
          {/* Language badge */}
          <span className="flex items-center gap-1.5 rounded-md bg-white/10 px-2 py-0.5 text-[11px] font-medium text-slate-300">
            <FileCode2 className="h-3 w-3" />
            {label}
          </span>
          {/* Filename */}
          {filename && (
            <span className="text-xs text-slate-500">{filename}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {/* Line count */}
          <span className="mr-2 text-[11px] text-slate-500">{lineCount} lines</span>
          {/* Wrap toggle */}
          <button
            onClick={() => setWrapEnabled(!wrapEnabled)}
            className={`rounded-md px-2 py-1 text-xs transition-colors ${
              wrapEnabled
                ? 'bg-white/10 text-white'
                : 'text-slate-400 hover:bg-white/10 hover:text-white'
            }`}
            aria-label="Toggle word wrap"
            title="Word wrap"
          >
            <WrapText className="h-3.5 w-3.5" />
          </button>
          {/* Download */}
          <button
            onClick={download}
            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            aria-label={`Download ${downloadFilename(language, filename)}`}
            title={`Download ${downloadFilename(language, filename)}`}
          >
            <Download className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Download</span>
          </button>
          {/* Copy */}
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
                  <span className="hidden sm:inline">Copy</span>
                </motion.span>
              )}
            </AnimatePresence>
          </button>
        </div>
      </div>

      {/* Code area with syntax highlighting */}
      <Highlight theme={themes.nightOwl} code={code.trimEnd()} language={language}>
        {({ tokens, getLineProps, getTokenProps }) => (
          <pre
            className={`m-0 overflow-x-auto bg-[#0f172a] p-4 text-[13px] leading-[1.65] ${
              wrapEnabled ? 'whitespace-pre-wrap break-words' : ''
            }`}
            style={{ margin: 0 }}
          >
            {tokens.map((line, i) => {
              const lineNum = i + 1;
              const isHighlighted = highlight.includes(lineNum);
              const lineProps = getLineProps({ line, key: i });
              return (
                <div
                  key={i}
                  {...lineProps}
                  onClick={() => copyLine(line.map((t) => t.content).join(''), lineNum)}
                  className={`${
                    lineProps.className || ''
                  } table-row cursor-pointer transition-colors hover:bg-white/5 ${
                    isHighlighted ? 'bg-amber-500/10 border-l-2 border-l-amber-400 -ml-0.5 pl-[calc(1rem-2px)]' : ''
                  }`}
                  title="Click to copy line"
                >
                  {showLineNumbers && (
                    <span className="table-cell select-none pr-4 text-right text-slate-600 [user-select:none]">
                      {lineNum}
                    </span>
                  )}
                  <span className="table-cell">
                    {line.map((token, key) => (
                      <span key={key} {...getTokenProps({ token })} />
                    ))}
                  </span>
                  {/* Line copy feedback */}
                  {copiedLine === lineNum && (
                    <span className="table-cell pl-3 text-[11px] text-emerald-400 opacity-70">
                      copied
                    </span>
                  )}
                </div>
              );
            })}
          </pre>
        )}
      </Highlight>
    </RevealOnView>
  );
}
