import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "orchestra",
  description: "AI agent orchestration — PoC",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-50 text-neutral-900">
        {children}
      </body>
    </html>
  );
}
