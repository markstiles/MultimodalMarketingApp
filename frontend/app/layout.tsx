import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sitecore Marketing Assistant",
  viewport: "width=device-width, initial-scale=1",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="h-screen overflow-hidden">{children}</body>
    </html>
  );
}
