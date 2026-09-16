import type { ButtonHTMLAttributes, PropsWithChildren } from 'react';

import { Icon } from './icons';
import type { IconName, StatusTone } from './types';

export function KyaMark() {
  return (
    <span className="kya-mark" aria-label="KYA-Platform">
      <img
        className="kya-mark__logo"
        src="/brand/kya-energy-group-logo.png"
        alt="KYA-Energy Group"
      />
      <strong>KYA-Platform</strong>
    </span>
  );
}

export function Button({
  children,
  className = '',
  ...props
}: PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>>) {
  return (
    <button className={`kya-button ${className}`} {...props}>
      {children}
    </button>
  );
}

export function IconButton({
  icon,
  label,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { icon: IconName; label: string }) {
  return (
    <button aria-label={label} className={`kya-icon-button ${className}`} title={label} {...props}>
      <Icon name={icon} />
    </button>
  );
}

export function StatusBadge({
  children,
  tone = 'neutral',
}: PropsWithChildren<{ tone?: StatusTone }>) {
  return (
    <span className={`kya-status kya-status--${tone}`}>
      <span aria-hidden="true" className="kya-status__dot" />
      {children}
    </span>
  );
}
