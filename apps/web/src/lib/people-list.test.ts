import { describe, expect, it } from "vitest";
import { listPeople, type PersonRow } from "./people-list";

const mk = (id: string, name: string, kind: PersonRow["kind"], className?: string): PersonRow => ({
  id,
  name,
  kind,
  className,
  active: true,
  deviceEnrolled: false,
});
const data = [
  mk("1", "Zed", "student", "Ten"),
  mk("2", "Amy", "teacher"),
  mk("3", "Bob Smith", "student", "Nine"),
  mk("10", "Cy", "staff"),
];

describe("listPeople", () => {
  it("sorts by name and paginates", () => {
    const r = listPeople(data, { page: 2 }, 2);
    expect(r.items.map((p) => p.name)).toEqual(["Cy", "Zed"]);
    expect(r.total).toBe(4);
    expect(r.pages).toBe(2);
    expect(r.page).toBe(2);
  });
  it("filters by kind, class and search (name or id)", () => {
    expect(listPeople(data, { kind: "student" }, 25).items).toHaveLength(2);
    expect(listPeople(data, { className: "Nine" }, 25).items.map((p) => p.id)).toEqual(["3"]);
    expect(listPeople(data, { q: "smith" }, 25).items.map((p) => p.id)).toEqual(["3"]);
    expect(listPeople(data, { q: "10" }, 25).items.map((p) => p.id)).toEqual(["10"]);
  });
  it("clamps the page", () => {
    expect(listPeople(data, { page: 99 }, 25).page).toBe(1);
    expect(listPeople(data, { page: -3 }, 25).page).toBe(1);
  });
});
