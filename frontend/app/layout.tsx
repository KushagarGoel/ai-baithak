import type { Metadata } from "next";
import "./globals.css";
import { AuthGuard } from "@/components/auth/AuthGuard";

export const metadata: Metadata = {
  title: "Agent Council - AI Deliberation Platform",
  description: "Configure your council and let them deliberate",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-background text-on-background">
        <AuthGuard>{children}</AuthGuard>
      </body>
    </html>
  );
}
