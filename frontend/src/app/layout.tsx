import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Water Guardian | Township operations", description: "Evidence-backed water-system investigations and operator-approved inspection tasks." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

