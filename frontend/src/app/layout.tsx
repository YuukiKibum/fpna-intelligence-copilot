import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Executive Finance Assistant",
  description: "Finance insight workspace for executive reporting",
  applicationName: "Executive Finance Assistant",
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon.ico",
    apple: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}