import "./globals.css";
import type { Metadata } from "next";
import { DM_Sans, JetBrains_Mono, Syne } from "next/font/google";
import { Sidebar } from "@/components/Sidebar";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  weight: ["400", "500", "600"],
  display: "swap",
});
const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI Workforce Platform",
  description: "Enterprise multi-agent AI workforce with chat & real-time voice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${dmSans.variable} ${jetbrainsMono.variable} ${syne.variable}`}
    >
      <body className="flex h-screen overflow-hidden bg-[#030712] font-sans">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-grid">{children}</main>
      </body>
    </html>
  );
}
