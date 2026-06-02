import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "PolyBOT Admin",
  description: "Polymarket trading bot control panel",
};

const NAV = [
  ["Overview", "/"],
  ["Strategies", "/strategies"],
  ["Signals", "/signals"],
  ["Positions", "/positions"],
  ["Markets", "/markets"],
  ["Whales", "/whales"],
  ["Backtest", "/backtest"],
  ["Risk", "/risk"],
  ["Logs", "/logs"],
  ["Settings", "/settings"],
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body>
        <div className="flex min-h-screen">
          <aside className="w-56 border-r border-border bg-panel p-4">
            <div className="mb-6 text-lg font-bold text-accent">PolyBOT</div>
            <nav className="flex flex-col gap-1">
              {NAV.map(([label, href]) => (
                <Link
                  key={href}
                  href={href}
                  className="rounded px-3 py-2 text-sm text-slate-300 hover:bg-border hover:text-white"
                >
                  {label}
                </Link>
              ))}
            </nav>
          </aside>
          <main className="flex-1 p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
