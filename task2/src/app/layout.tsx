import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Companies App",
  description: "Справочник компаний поверх PostgreSQL",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body style={{ margin: 0, background: "#fafafa" }}>{children}</body>
    </html>
  );
}
