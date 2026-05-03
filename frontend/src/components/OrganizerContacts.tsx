"use client";

export interface OrganizerContacts {
  phones?: string[];
  emails?: string[];
  inn?: string;
  kpp?: string;
  ogrn?: string;
  contact_person?: string;
  address?: string;
}

export default function OrganizerContactsCard({
  organizerName,
  contacts,
}: {
  organizerName?: string | null;
  contacts?: OrganizerContacts | null;
}) {
  if (!contacts && !organizerName) return null;
  const c = contacts || {};
  const hasAny =
    organizerName ||
    (c.phones && c.phones.length) ||
    (c.emails && c.emails.length) ||
    c.inn || c.address || c.contact_person;
  if (!hasAny) return null;

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 12, padding: 16,
    }}>
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>
        🏛 Контакты администрации
      </div>

      {organizerName && (
        <div style={{ fontSize: 13, marginBottom: 10, lineHeight: 1.4, color: "var(--text-2)" }}>
          {organizerName}
        </div>
      )}

      {c.contact_person && (
        <Row label="Ответственный" value={c.contact_person} />
      )}

      {c.phones && c.phones.length > 0 && (
        <Row
          label="Телефон"
          value={
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {c.phones.map((p, i) => (
                <a key={i} href={`tel:${p.replace(/\D/g, "")}`} style={{ color: "var(--primary)", textDecoration: "none" }}>
                  {p}
                </a>
              ))}
            </div>
          }
        />
      )}

      {c.emails && c.emails.length > 0 && (
        <Row
          label="Email"
          value={
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {c.emails.map((e, i) => (
                <a key={i} href={`mailto:${e}`} style={{ color: "var(--primary)", textDecoration: "none" }}>
                  {e}
                </a>
              ))}
            </div>
          }
        />
      )}

      {c.address && <Row label="Адрес" value={c.address} />}

      {(c.inn || c.kpp || c.ogrn) && (
        <Row
          label="Реквизиты"
          value={
            <div style={{ fontSize: 12, color: "var(--text-3)" }}>
              {c.inn && <span>ИНН {c.inn}</span>}
              {c.kpp && <span>{c.inn ? " · " : ""}КПП {c.kpp}</span>}
              {c.ogrn && <span>{(c.inn || c.kpp) ? " · " : ""}ОГРН {c.ogrn}</span>}
            </div>
          }
        />
      )}

      <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 10, lineHeight: 1.4 }}>
        💡 Свяжитесь с отделом земельных отношений напрямую — узнайте ВРИ,
        обременения, доступ к коммуникациям, перспективы выкупа.
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 12, marginBottom: 8, fontSize: 13 }}>
      <span style={{ color: "var(--text-3)", minWidth: 100, flexShrink: 0 }}>{label}</span>
      <span style={{ flex: 1, wordBreak: "break-word" }}>{value}</span>
    </div>
  );
}
