export type PersonRow = {
  id: string;
  name: string;
  kind: "staff" | "teacher" | "student";
  className?: string;
  section?: string;
  phone?: string;
  active: boolean;
  deviceEnrolled: boolean;
};

export type PeopleQuery = { q?: string; kind?: string; className?: string; page?: number };

export const PAGE_SIZE = 25;

export function listPeople(all: PersonRow[], query: PeopleQuery, pageSize = PAGE_SIZE) {
  const q = (query.q ?? "").trim().toLowerCase();
  const filtered = all
    .filter((p) => !query.kind || p.kind === query.kind)
    .filter((p) => !query.className || p.className === query.className)
    .filter((p) => !q || p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q))
    .sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const requested = Number.isFinite(query.page) ? Math.floor(query.page as number) : 1;
  const page = requested >= 1 && requested <= pages ? requested : 1;
  return { items: filtered.slice((page - 1) * pageSize, page * pageSize), total: filtered.length, page, pages };
}
