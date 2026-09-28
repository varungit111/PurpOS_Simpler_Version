import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PurpOS",
  description: "A foundation prototype for the SOI self-service journey."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
