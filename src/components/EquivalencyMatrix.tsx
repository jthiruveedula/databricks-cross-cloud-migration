import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import CloudLogo from './CloudLogo';

interface Row {
  concept: string;
  azure: string;
  aws: string;
  gcp: string;
}

interface Category {
  key: string;
  label: string;
  rows: Row[];
}

// Same content as the six stacked markdown tables this replaces -- real construct names,
// nothing invented. Grouped behind a category selector instead of one continuous scroll of
// near-identical tables, with the cloud brand marks in the header instead of repeated
// "Azure Databricks / AWS Databricks / GCP Databricks" text on every table.
const CATEGORIES: Category[] = [
  {
    key: 'identity',
    label: 'Account & identity',
    rows: [
      { concept: 'Top-level boundary', azure: 'Azure AD tenant + Databricks account', aws: 'AWS account + Databricks account', gcp: 'GCP project + Databricks account' },
      { concept: 'Billing', azure: 'Azure subscription', aws: 'AWS account', gcp: 'GCP project' },
      { concept: 'Workspace identity', azure: 'Managed identity / service principal', aws: 'IAM role / instance profile', gcp: 'Service account' },
      { concept: 'User federation', azure: 'Entra ID (Azure AD)', aws: 'IAM Identity Center / SSO', gcp: 'Google Cloud IAM / Workspace SSO' },
      { concept: 'Service principal', azure: 'Entra ID app registration', aws: 'IAM role with external ID', gcp: 'Service account with key or impersonation' },
      { concept: 'SCIM provisioning', azure: 'Entra ID provisioning', aws: 'IAM Identity Center SCIM', gcp: 'Google Workspace / Cloud Identity SCIM' },
    ],
  },
  {
    key: 'storage',
    label: 'Storage',
    rows: [
      { concept: 'Object storage', azure: 'ADLS Gen2', aws: 'S3', gcp: 'Cloud Storage (GCS)' },
      { concept: 'Filesystem prefix', azure: 'abfss://container@account.dfs.core.net', aws: 's3://bucket/path', gcp: 'gs://bucket/path' },
      { concept: 'UC external location', azure: 'Storage credential + ADLS path', aws: 'Storage credential + S3 path', gcp: 'Storage credential + GCS path' },
      { concept: 'Access delegation', azure: 'Managed identity / SAS token', aws: 'IAM role on cluster / instance profile', gcp: 'Service account attached to cluster' },
      { concept: 'Encryption', azure: 'SSE with Microsoft-managed or CMK in Key Vault', aws: 'SSE-S3 / SSE-KMS', gcp: 'Customer-managed encryption keys (CMEK)' },
    ],
  },
  {
    key: 'networking',
    label: 'Networking',
    rows: [
      { concept: 'Virtual network', azure: 'VNet', aws: 'VPC', gcp: 'VPC' },
      { concept: 'Private control plane', azure: 'Private Link', aws: 'PrivateLink', gcp: 'Private Service Connect (PSC)' },
      { concept: 'Subnets', azure: 'Public + private subnet delegation', aws: 'Public + private subnets', gcp: 'Subnet with private Google Access' },
      { concept: 'NAT / egress', azure: 'Azure NAT Gateway', aws: 'NAT Gateway', gcp: 'Cloud NAT' },
      { concept: 'DNS', azure: 'Azure Private DNS', aws: 'Route53 private', gcp: 'Cloud DNS' },
      { concept: 'Secure cluster connectivity', azure: 'No public IPs / secure cluster connectivity', aws: 'No public IP', gcp: 'Private Google Access' },
    ],
  },
  {
    key: 'secrets',
    label: 'Secrets & keys',
    rows: [
      { concept: 'Secret backend', azure: 'Azure Key Vault', aws: 'AWS Secrets Manager / Parameter Store', gcp: 'Secret Manager' },
      { concept: 'Key management', azure: 'Azure Key Vault', aws: 'AWS KMS', gcp: 'Cloud KMS' },
      { concept: 'UC storage credential secret', azure: 'Key Vault-backed scope', aws: 'Secrets Manager-backed scope', gcp: 'Secret Manager-backed scope' },
    ],
  },
  {
    key: 'compute',
    label: 'Compute & orchestration',
    rows: [
      { concept: 'VM instances', azure: 'Azure VM', aws: 'EC2', gcp: 'Compute Engine' },
      { concept: 'Spot / preemptible', azure: 'Spot VMs / spot eviction', aws: 'Spot Instances', gcp: 'Preemptible VMs' },
      { concept: 'Scheduler', azure: 'Databricks Workflows', aws: 'Databricks Workflows', gcp: 'Databricks Workflows' },
      { concept: 'External orchestrator', azure: 'Azure Data Factory, Airflow', aws: 'Glue, Airflow, Step Functions', gcp: 'Cloud Composer, Airflow' },
      { concept: 'Container registry', azure: 'ACR', aws: 'ECR', gcp: 'Artifact Registry' },
    ],
  },
  {
    key: 'monitoring',
    label: 'Monitoring & audit',
    rows: [
      { concept: 'Control-plane logs', azure: 'Diagnostic logs', aws: 'Account log delivery', gcp: 'Cloud Logging' },
      { concept: 'Audit', azure: 'Azure Monitor / Log Analytics', aws: 'CloudWatch / S3', gcp: 'Cloud Logging / BigQuery' },
      { concept: 'Billing export', azure: 'Cost Management', aws: 'CUR', gcp: 'Cloud Billing export' },
      { concept: 'System tables', azure: 'Enabled at account', aws: 'Enabled at account', gcp: 'Enabled at account' },
    ],
  },
];

export default function EquivalencyMatrix() {
  const [active, setActive] = useState(0);
  const category = CATEGORIES[active];

  return (
    <div className="my-6 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)]">
      <div className="flex flex-wrap gap-1 border-b border-[var(--border)] p-2">
        {CATEGORIES.map((c, i) => (
          <button
            key={c.key}
            onClick={() => setActive(i)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              active === i
                ? 'bg-[var(--accent-soft)] text-[var(--accent)]'
                : 'text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]'
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={category.key}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.15, ease: 'easeOut' }}
          className="overflow-x-auto"
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)]">
                <th className="p-3 text-left font-semibold text-[var(--ink)]">Concept</th>
                <th className="p-3 text-left"><CloudLogo cloud="azure" size="sm" showLabel /></th>
                <th className="p-3 text-left"><CloudLogo cloud="aws" size="sm" showLabel /></th>
                <th className="p-3 text-left"><CloudLogo cloud="gcp" size="sm" showLabel /></th>
              </tr>
            </thead>
            <tbody>
              {category.rows.map((row, i) => (
                <tr key={row.concept} className={i % 2 === 1 ? 'bg-[var(--surface)]' : ''}>
                  <td className="p-3 font-medium text-[var(--ink)]">{row.concept}</td>
                  <td className="p-3 text-[var(--ink-muted)]">{row.azure}</td>
                  <td className="p-3 text-[var(--ink-muted)]">{row.aws}</td>
                  <td className="p-3 text-[var(--ink-muted)]">{row.gcp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
