import Link from "next/link";

export default function Home() {
  return (
    <main
      style={{
        maxWidth: 640,
        margin: "4rem auto",
        padding: "0 1.5rem",
        fontFamily: "system-ui, sans-serif",
        textAlign: "center",
      }}
    >
      <h1 style={{ fontSize: "1.75rem", marginBottom: "0.5rem" }}>
        Companies App
      </h1>
      <p style={{ color: "#666", marginBottom: "1.5rem" }}>
        Мини-фича поверх базы из задачи 1 (PostgreSQL + Next.js App Router)
      </p>
      <Link
        href="/companies"
        style={{
          display: "inline-block",
          padding: "0.7rem 1.4rem",
          background: "#2563eb",
          color: "#fff",
          borderRadius: 8,
          textDecoration: "none",
          fontWeight: 600,
        }}
      >
        Перейти к справочнику →
      </Link>
    </main>
  );
}
