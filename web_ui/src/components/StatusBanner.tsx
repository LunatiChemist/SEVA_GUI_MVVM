interface StatusBannerProps {
  text?: string;
}

export function StatusBanner({ text }: StatusBannerProps) {
  if (!text) {
    return null;
  }
  return <div className="status-banner">{text}</div>;
}
