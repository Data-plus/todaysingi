export type IconName = "grid" | "box" | "activity" | "send" | "chart" | "settings" | "plus" | "arrow" | "play" | "github" | "menu" | "search" | "refresh" | "close" | "logout" | "external" | "calendar" | "link" | "alert" | "check" | "rotate" | "cancel" | "cpu" | "chevron";

const paths: Record<IconName, React.ReactNode> = {
  grid: <><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></>,
  box: <><path d="m21 8-9-5-9 5 9 5 9-5Z"/><path d="m3 8 9 5 9-5"/><path d="M3 8v8l9 5 9-5V8"/></>,
  activity: <path d="M3 12h4l3-8 4 16 3-8h4"/>,
  send: <><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></>,
  chart: <><path d="M4 19V9"/><path d="M10 19V5"/><path d="M16 19v-7"/><path d="M22 19H2"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
  plus: <><path d="M12 5v14"/><path d="M5 12h14"/></>,
  arrow: <><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></>,
  play: <path d="m8 5 11 7-11 7Z"/>,
  github: <><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3.3-.4 6.7-1.6 6.7-7.3A5.7 5.7 0 0 0 19.2 3.3 5.4 5.4 0 0 0 19.1 1S17.9.7 15 2.5a13.4 13.4 0 0 0-6 0C6.1.7 4.9 1 4.9 1a5.4 5.4 0 0 0-.1 2.3 5.7 5.7 0 0 0-1.5 4c0 5.6 3.4 6.8 6.7 7.2A4.8 4.8 0 0 0 9 18v4"/><path d="M9 18c-4.5 2-5-2-7-2"/></>,
  menu: <><path d="M4 7h16"/><path d="M4 12h16"/><path d="M4 17h16"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  refresh: <><path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/></>,
  close: <><path d="m6 6 12 12"/><path d="m18 6-12 12"/></>,
  logout: <><path d="M10 17l5-5-5-5"/><path d="M15 12H3"/><path d="M14 3h5a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-5"/></>,
  external: <><path d="M14 3h7v7"/><path d="m10 14 11-11"/><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
  link: <><path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.1-1.1"/></>,
  alert: <><path d="M10.3 3.6 2.2 18a2 2 0 0 0 1.8 3h16a2 2 0 0 0 1.8-3L13.7 3.6a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  rotate: <><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v8h8"/></>,
  cancel: <><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/></>,
  cpu: <><rect x="7" y="7" width="10" height="10" rx="1"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/></>,
  chevron: <path d="m9 18 6-6-6-6"/>,
};

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
