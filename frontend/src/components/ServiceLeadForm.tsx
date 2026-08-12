"use client";
import { useState } from "react";
import { api } from "@/lib/api";

/* Форма заявки на услугу. Живёт отдельно, потому что нужна и на общей странице
   услуг, и на региональных лендингах под объявления.

   Регион уходит в comment, а не отдельным полем: эндпоинт /api/services/lead
   принимает фиксированный набор полей, и лишнее он молча отбрасывает — а
   потерять регион в заявке с рекламы нельзя. */

type Props = {
  defaultPackage?: string;
  regionName?: string;
  title?: string;
};

export default function ServiceLeadForm({
  defaultPackage = "turnkey",
  regionName,
  title = "Оставить заявку",
}: Props) {
  const [form, setForm] = useState({ name: "", contact: "", comment: "" });
  const [pkg, setPkg] = useState(defaultPackage);
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    if (form.name.trim().length < 2 || form.contact.trim().length < 5) {
      setErr("Заполните имя и контакт — телефон или @telegram");
      return;
    }
    setSending(true);
    try {
      const comment = [
        regionName ? `Регион: ${regionName}.` : "",
        form.comment.trim(),
      ].filter(Boolean).join(" ");
      await api.post("/api/services/lead", {
        name: form.name.trim(),
        contact: form.contact.trim(),
        package: pkg,
        comment: comment || null,
      });
      setSent(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message
        : "Не отправилось — напишите в Telegram @torgi_zemli");
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <div id="request-form" style={{
        background: "var(--surface)", border: "1px solid var(--primary)",
        borderRadius: 14, padding: 28, textAlign: "center",
      }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
        <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 6 }}>Заявка принята</div>
        <div style={{ color: "var(--text-2)", lineHeight: 1.6 }}>
          Свяжусь с вами в течение дня. Если удобнее сразу — пишите в Telegram{" "}
          <a href="https://t.me/torgi_zemli" style={{ color: "var(--primary)" }}>@torgi_zemli</a>.
        </div>
      </div>
    );
  }

  const input: React.CSSProperties = {
    width: "100%", padding: "11px 13px", borderRadius: 9,
    border: "1px solid var(--border)", background: "var(--bg)",
    color: "var(--text)", fontSize: 15,
  };

  return (
    <form id="request-form" onSubmit={submit} style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 14, padding: 24, display: "flex",
      flexDirection: "column", gap: 12,
    }}>
      <div style={{ fontWeight: 700, fontSize: 19 }}>{title}</div>

      <select className="select" value={pkg} onChange={e => setPkg(e.target.value)} style={input}>
        <option value="select">Подбор участков — без участия в торгах</option>
        <option value="turnkey">Участие в торгах под ключ</option>
        <option value="hectare">Дальневосточный / Арктический гектар</option>
        <option value="investor">Инвестору — поток лотов</option>
      </select>

      <input style={input} placeholder="Как к вам обращаться"
        value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
      <input style={input} placeholder="Телефон или @telegram"
        value={form.contact} onChange={e => setForm(f => ({ ...f, contact: e.target.value }))} />
      <textarea style={{ ...input, minHeight: 84, resize: "vertical" }}
        placeholder={regionName
          ? `Что ищете: район, площадь, бюджет, для чего участок`
          : "Что ищете: регион, площадь, бюджет, для чего участок"}
        value={form.comment} onChange={e => setForm(f => ({ ...f, comment: e.target.value }))} />

      {err && <div style={{ color: "#dc2626", fontSize: 14 }}>{err}</div>}

      <button className="btn btn-primary" disabled={sending} style={{ padding: "12px 18px", fontSize: 16 }}>
        {sending ? "Отправляю…" : "Отправить заявку"}
      </button>
      <div style={{ fontSize: 12.5, color: "var(--text-2)", lineHeight: 1.5 }}>
        Отвечаю лично в течение дня. Ничего не списываем и не подписываем без вашего согласия.
      </div>
    </form>
  );
}
