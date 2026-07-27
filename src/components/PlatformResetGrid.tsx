import React from 'react';
import CloudLogo from './CloudLogo';

interface Row {
  label: string;
  azure: string;
  aws: string;
  gcp: string;
}

const ROWS: Row[] = [
  { label: 'Account boundary', azure: 'Tenant / subscription', aws: 'Account', gcp: 'Project' },
  { label: 'Identity', azure: 'Entra ID', aws: 'IAM', gcp: 'IAM' },
  { label: 'Storage', azure: 'ADLS Gen2', aws: 'S3', gcp: 'GCS' },
  { label: 'Networking', azure: 'VNet, private endpoints', aws: 'VPC, PrivateLink', gcp: 'VPC, PSC' },
];

export default function PlatformResetGrid() {
  return (
    <div className="my-6 overflow-x-auto rounded-xl border border-[var(--border)]">
      <table className="w-full min-w-[520px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface-elevated)]">
            <th className="p-3 text-left font-semibold text-[var(--ink)]">Reset per cloud</th>
            <th className="p-3 text-left font-semibold text-[var(--ink)]">
              <CloudLogo cloud="azure" size="sm" showLabel />
            </th>
            <th className="p-3 text-left font-semibold text-[var(--ink)]">
              <CloudLogo cloud="aws" size="sm" showLabel />
            </th>
            <th className="p-3 text-left font-semibold text-[var(--ink)]">
              <CloudLogo cloud="gcp" size="sm" showLabel />
            </th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row, i) => (
            <tr key={row.label} className={i < ROWS.length - 1 ? 'border-b border-[var(--border)]' : ''}>
              <td className="p-3 font-medium text-[var(--ink)]">{row.label}</td>
              <td className="p-3 text-[var(--ink-muted)]">{row.azure}</td>
              <td className="p-3 text-[var(--ink-muted)]">{row.aws}</td>
              <td className="p-3 text-[var(--ink-muted)]">{row.gcp}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-[var(--border)] bg-[var(--surface-elevated)] p-3 text-xs text-[var(--ink-subtle)]">
        Unity Catalog is the one governance layer that spans all three — but metastores stay region-specific and account-scoped.
      </p>
    </div>
  );
}
