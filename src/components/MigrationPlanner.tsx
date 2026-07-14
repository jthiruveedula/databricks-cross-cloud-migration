import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowRight,
  BookOpen,
  CheckCircle,
  ClipboardList,
  Cloud,
  Cpu,
  Database,
  FileCode,
  Globe,
  LayoutList,
  Map,
  Network,
  Plane,
  RefreshCw,
  RotateCcw,
  Shield,
  Terminal,
  Workflow,
} from 'lucide-react';
import CloudLogo from './CloudLogo.tsx';
import ToolLogo from './ToolLogo.tsx';
import { withBase } from '../lib/paths';

type Cloud = 'aws' | 'azure' | 'gcp';

interface CloudMeta {
  label: string;
  color: string;
  bg: string;
}

const CLOUDS: Record<Cloud, CloudMeta> = {
  aws: { label: 'AWS', color: 'text-orange-400', bg: 'bg-orange-500/10' },
  azure: { label: 'Azure', color: 'text-sky-400', bg: 'bg-sky-500/10' },
  gcp: { label: 'GCP', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
};

const MAPPING_SLUG: Record<string, string> = {
  'azure-aws': 'cloud-mappings/azure-to-aws',
  'azure-gcp': 'cloud-mappings/azure-to-gcp',
  'aws-azure': 'cloud-mappings/aws-to-azure',
  'aws-gcp': 'cloud-mappings/aws-to-gcp',
  'gcp-azure': 'cloud-mappings/gcp-to-azure',
  'gcp-aws': 'cloud-mappings/gcp-to-aws',
};

interface Phase {
  icon: React.ElementType;
  title: string;
  links: { label: string; href: string }[];
}

const PHASES: Phase[] = [
  {
    icon: ClipboardList,
    title: 'Discover',
    links: [
      { label: 'Workspace inventory', href: '/discovery/workspace-inventory' },
      { label: 'Asset inventory', href: '/discovery/asset-inventory' },
      { label: 'Dependency mapping', href: '/discovery/dependency-mapping' },
      { label: 'Risk assessment', href: '/discovery/risk-assessment' },
    ],
  },
  {
    icon: Shield,
    title: 'Govern & secure',
    links: [
      { label: 'Unity Catalog strategy', href: '/governance/unity-catalog-strategy' },
      { label: 'Metastore migration', href: '/governance/metastore-migration' },
      { label: 'IAM mapping', href: '/security/iam-mapping' },
      { label: 'Network security', href: '/security/network-security' },
    ],
  },
  {
    icon: Cpu,
    title: 'Compute & pipelines',
    links: [
      { label: 'Cluster migration', href: '/compute/cluster-migration' },
      { label: 'Runtime upgrade', href: '/compute/runtime-upgrade' },
      { label: 'Workflows and jobs', href: '/pipelines/workflows-jobs' },
      { label: 'CI/CD promotion', href: '/pipelines/cicd-promotion' },
    ],
  },
  {
    icon: RefreshCw,
    title: 'Execute & validate',
    links: [
      { label: 'Wave planning', href: '/execution/wave-planning' },
      { label: 'Cutover', href: '/execution/cutover' },
      { label: 'Data reconciliation', href: '/validation/data-reconciliation' },
      { label: 'Security validation', href: '/validation/security-validation' },
    ],
  },
  {
    icon: FileCode,
    title: 'Templates & scripts',
    links: [
      { label: 'Checklists', href: '/templates/checklists' },
      { label: 'Terraform patterns', href: '/templates/terraform-patterns' },
      { label: 'Sample scripts', href: '/templates/sample-scripts' },
      { label: 'Risk register', href: '/templates/risk-register' },
    ],
  },
];

const TOOLS = [
  { icon: Terminal, label: 'Databricks CLI', href: 'https://docs.databricks.com/aws/en/dev-tools/cli/' },
  { icon: Database, label: 'UCX', href: 'https://github.com/databrickslabs/ucx' },
  { icon: FileCode, label: 'Terraform provider', href: 'https://registry.terraform.io/providers/databricks/databricks/latest/docs' },
  { icon: RefreshCw, label: 'Delta Deep Clone', href: 'https://docs.databricks.com/aws/en/delta/deep-clone/' },
  { icon: Network, label: 'Cloud CLIs', href: '/templates/sample-scripts' },
  { icon: Cloud, label: 'Delta Sharing', href: 'https://docs.databricks.com/aws/en/delta-sharing/' },
];

function emphasis(source: Cloud, target: Cloud): string {
  if (source === target) {
    return 'Subscription/account boundaries, cross-region replication, and IAM standardization.';
  }
  const pair = `${source}-${target}`;
  switch (pair) {
    case 'azure-aws':
    case 'aws-azure':
      return 'Entra ID ↔ AWS IAM federation, ADLS Gen2 ↔ S3 paths, and VNet ↔ VPC private endpoints.';
    case 'azure-gcp':
    case 'gcp-azure':
      return 'Entra ID ↔ Google Cloud Identity, ADLS Gen2 ↔ GCS paths, and VNet ↔ VPC/PSC.';
    case 'aws-gcp':
    case 'gcp-aws':
      return 'AWS IAM ↔ GCP IAM roles, S3 ↔ GCS paths, and VPC ↔ VPC/PSC peering.';
    default:
      return 'Identity, storage, networking, and metastore alignment.';
  }
}

export default function MigrationPlanner() {
  const [source, setSource] = useState<Cloud | ''>('');
  const [target, setTarget] = useState<Cloud | ''>('');
  const [submitted, setSubmitted] = useState(false);

  const plan = useMemo(() => {
    if (!source || !target) return null;
    const crossCloud = source !== target;
    const mappingSlug = MAPPING_SLUG[`${source}-${target}`];
    return {
      crossCloud,
      mappingSlug,
      strategyTitle: crossCloud
        ? 'Cross-cloud platform reset'
        : 'Same-cloud landing-zone move',
      strategyBody: crossCloud
        ? 'Metastores, identities, storage endpoints, and networks are not portable across clouds. Recreate the target foundation, replicate data, and re-register assets in Unity Catalog.'
        : 'The cloud primitives stay the same, so lift-and-shift is possible. Still treat the move as a chance to standardize accounts, regions, and governance.',
      approach: crossCloud
        ? `A deliberate reset across ${CLOUDS[source].label} and ${CLOUDS[target].label}. ${emphasis(source, target)}`
        : `Re-home the workspace inside ${CLOUDS[source].label}. ${emphasis(source, target)}`,
    };
  }, [source, target]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 md:p-8"
    >
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="mb-2 flex items-center gap-2 text-2xl font-semibold text-[var(--ink)]">
            <Map className="h-6 w-6 text-[var(--accent)]" />
            Migration pathfinder
          </h2>
          <p className="max-w-2xl text-[var(--ink-muted)]">
            Pick a source and target cloud to generate a tailored migration path, toolset, and recommended runbook pages.
          </p>
        </div>
        <a
          href={withBase('/overview/decision-framework')}
          className="inline-flex items-center gap-1 text-sm font-medium text-[var(--accent)] hover:underline"
        >
          Read the decision framework <ArrowRight className="h-4 w-4" />
        </a>
      </div>

      <motion.form
        onSubmit={(e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          const s = data.get('source') as Cloud;
          const t = data.get('target') as Cloud;
          setSource(s);
          setTarget(t);
          setSubmitted(true);
        }}
        whileHover={{ scale: 1.005 }}
        className="grid gap-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 md:grid-cols-[1fr_auto_1fr_auto] md:items-center"
      >
        <label className="flex flex-col gap-2 text-sm font-medium text-[var(--ink)]">
          Source cloud
          <select
            name="source"
            required
            defaultValue=""
            className="rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-4 py-2.5 text-[var(--ink)] outline-none ring-[var(--accent)] focus:ring-2"
          >
            <option value="" disabled>Choose source</option>
            {(['aws', 'azure', 'gcp'] as Cloud[]).map((c) => (
              <option key={c} value={c}>
                {CLOUDS[c].label}
              </option>
            ))}
          </select>
        </label>

        <div className="flex justify-center">
          <motion.div
            animate={{ x: [0, 4, 0] }}
            transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
            className="rounded-full border border-[var(--border)] bg-[var(--surface-elevated)] p-2 text-[var(--ink-muted)]"
          >
            <Plane className="h-5 w-5 rotate-90 md:rotate-0" />
          </motion.div>
        </div>

        <label className="flex flex-col gap-2 text-sm font-medium text-[var(--ink)]">
          Target cloud
          <select
            name="target"
            required
            defaultValue=""
            className="rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-4 py-2.5 text-[var(--ink)] outline-none ring-[var(--accent)] focus:ring-2"
          >
            <option value="" disabled>Choose target</option>
            {(['aws', 'azure', 'gcp'] as Cloud[]).map((c) => (
              <option key={c} value={c}>
                {CLOUDS[c].label}
              </option>
            ))}
          </select>
        </label>

        <motion.button
          type="submit"
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-5 py-2.5 font-medium text-white shadow-glow transition-shadow hover:shadow-glow md:w-auto"
        >
          Build my path <ArrowRight className="h-4 w-4" />
        </motion.button>
      </motion.form>

      <AnimatePresence>
        {submitted && plan && source && target && (
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            transition={{ duration: 0.4 }}
            className="mt-8"
          >
            <motion.div
              initial={{ scale: 0.98 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.35 }}
              className="mb-6 rounded-xl border border-[var(--border)] bg-gradient-to-br from-[var(--surface)] to-[var(--surface-elevated)] p-6"
            >
              <div className="mb-4 flex flex-wrap items-center gap-4">
                <CloudLogo cloud={source} showLabel />
                <motion.div
                  animate={{ x: [0, 6, 0] }}
                  transition={{ repeat: Infinity, duration: 1.6, ease: 'easeInOut' }}
                >
                  <ArrowRight className="h-6 w-6 text-[var(--accent)]" />
                </motion.div>
                <CloudLogo cloud={target} showLabel />
              </div>
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
                    plan.crossCloud ? 'bg-rose-500/10 text-rose-400' : 'bg-emerald-500/10 text-emerald-400'
                  }`}
                >
                  {plan.crossCloud ? 'Platform reset' : 'Lift-and-shift eligible'}
                </span>
                <h3 className="text-xl font-semibold text-[var(--ink)]">{plan.strategyTitle}</h3>
              </div>
              <p className="mb-4 text-[var(--ink-muted)]">{plan.strategyBody}</p>
              <p className="text-sm text-[var(--ink)]">
                <span className="font-semibold">Approach:</span> {plan.approach}
              </p>
            </motion.div>

            <div className="grid gap-6 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <h4 className="mb-4 flex items-center gap-2 font-semibold text-[var(--ink)]">
                  <LayoutList className="h-5 w-5 text-[var(--accent)]" />
                  Recommended runbook path
                </h4>
                <div className="space-y-4">
                  {plan.mappingSlug && (
                    <motion.a
                      href={withBase(`/${plan.mappingSlug}`)}
                      whileHover={{ scale: 1.01, x: 4 }}
                      className="group flex items-start gap-4 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 transition-colors hover:border-[var(--accent)]/50 hover:bg-[var(--surface-hover)]"
                    >
                      <div className="rounded-lg bg-[var(--accent-soft)] p-2 text-[var(--accent)]">
                        <Globe className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="font-medium text-[var(--ink)] group-hover:text-[var(--accent)]">
                          Start with the {CLOUDS[source].label} → {CLOUDS[target].label} cloud mapping
                        </div>
                        <div className="text-sm text-[var(--ink-muted)]">
                          See construct equivalencies, IAM mapping, storage semantics, and networking differences.
                        </div>
                      </div>
                      <ArrowRight className="ml-auto h-5 w-5 shrink-0 text-[var(--ink-muted)] group-hover:text-[var(--accent)]" />
                    </motion.a>
                  )}

                  {PHASES.map((phase, idx) => (
                    <motion.div
                      key={phase.title}
                      initial={{ opacity: 0, x: -12 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.08 }}
                      className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"
                    >
                      <div className="mb-3 flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--accent-soft)] text-sm font-bold text-[var(--accent)]">
                          {idx + 1}
                        </div>
                        <h5 className="flex items-center gap-2 font-semibold text-[var(--ink)]">
                          <phase.icon className="h-4 w-4 text-[var(--accent)]" />
                          {phase.title}
                        </h5>
                      </div>
                      <div className="flex flex-wrap gap-2 pl-11">
                        {phase.links.map((link) => (
                          <a
                            key={link.href}
                            href={withBase(link.href)}
                            className="rounded-full border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-1 text-sm text-[var(--ink)] transition-colors hover:border-[var(--accent)]/50 hover:text-[var(--accent)]"
                          >
                            {link.label}
                          </a>
                        ))}
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="mb-4 flex items-center gap-2 font-semibold text-[var(--ink)]">
                  <Terminal className="h-5 w-5 text-[var(--accent)]" />
                  Suggested toolset
                </h4>
                <div className="space-y-3">
                  {TOOLS.map((tool, idx) => (
                    <motion.a
                      key={tool.label}
                      href={tool.href.startsWith('http') ? tool.href : withBase(tool.href)}
                      target={tool.href.startsWith('http') ? '_blank' : undefined}
                      rel={tool.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                      initial={{ opacity: 0, x: 12 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.08 }}
                      whileHover={{ scale: 1.03, x: 4 }}
                      className="group flex items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 transition-colors hover:border-[var(--accent)]/50 hover:bg-[var(--surface-hover)]"
                    >
                      <ToolLogo name={tool.label} />
                      <span className="text-sm font-medium text-[var(--ink)] group-hover:text-[var(--accent)]">{tool.label}</span>
                      <ArrowRight className="ml-auto h-4 w-4 shrink-0 text-[var(--ink-muted)] opacity-0 transition-all group-hover:translate-x-1 group-hover:text-[var(--accent)] group-hover:opacity-100" />
                    </motion.a>
                  ))}
                </div>

              <motion.div
                whileHover={{ scale: 1.02 }}
                className="mt-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"
              >
                <h5 className="mb-2 flex items-center gap-2 font-semibold text-[var(--ink)]">
                  <RotateCcw className="h-4 w-4 text-[var(--accent)]" />
                  Rollback ready?
                </h5>
                <p className="mb-3 text-sm text-[var(--ink-muted)]">
                  Keep source workspaces online, preserve DBFS and metastore backups, and validate data before DNS cutover.
                </p>
                <a
                  href={withBase('/execution/rollback')}
                  className="inline-flex items-center gap-1 text-sm font-medium text-[var(--accent)] hover:underline"
                >
                  Open rollback guide <ArrowRight className="h-4 w-4" />
                </a>
              </motion.div>

              <motion.a
                href={withBase('/execution/wave-planning')}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.98 }}
                className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-3 font-medium text-white shadow-glow transition-shadow hover:shadow-glow"
              >
                <BookOpen className="h-4 w-4" />
                Start wave planning
              </motion.a>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
    </motion.div>
  );
}
