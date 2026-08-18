import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Automated Literature Review",
  description: "AI-powered research paper analysis system — Phase 0",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
