import { Document, Page, StyleSheet, Text, View } from "@react-pdf/renderer";
import type { PersonReport } from "@/lib/person-report";

export type ReportPerson = {
  id: string;
  name: string;
  kind: string;
  className?: string;
  section?: string;
  phone?: string;
  fatherPhone?: string;
  motherPhone?: string;
};

const s = StyleSheet.create({
  page: { padding: 32, fontSize: 10, fontFamily: "Helvetica" },
  org: { fontSize: 16, fontFamily: "Helvetica-Bold" },
  title: { fontSize: 12, marginBottom: 10, color: "#444444" },
  block: { marginBottom: 10 },
  summary: { flexDirection: "row", marginBottom: 10 },
  cell: { marginRight: 14 },
  tableHead: { flexDirection: "row", borderBottomWidth: 1, borderColor: "#000000", paddingBottom: 3, fontFamily: "Helvetica-Bold" },
  row: { flexDirection: "row", paddingVertical: 2, borderBottomWidth: 0.5, borderColor: "#cccccc" },
  c1: { width: "20%" },
  c2: { width: "14%" },
  c3: { width: "14%" },
  c4: { width: "22%" },
  c5: { width: "30%" },
});

export function PersonReportDocument(props: {
  orgName: string;
  person: ReportPerson;
  range: { from: string; to: string };
  report: PersonReport;
}) {
  const { orgName, person, range, report } = props;
  const phones = [person.phone, person.fatherPhone, person.motherPhone].filter(Boolean).join(" / ");
  const klass = [person.className, person.section].filter(Boolean).join(" ");
  const { summary } = report;
  return (
    <Document title={`Attendance report - ${person.name}`}>
      <Page size="A4" style={s.page}>
        <Text style={s.org}>{orgName}</Text>
        <Text style={s.title}>Attendance report</Text>
        <View style={s.block}>
          <Text>
            {person.name} (ID {person.id}) - {person.kind}
          </Text>
          {klass ? <Text>Class/Section: {klass}</Text> : null}
          {phones ? <Text>Phones: {phones}</Text> : null}
          <Text>
            Period: {range.from} to {range.to}
          </Text>
        </View>
        <View style={s.summary}>
          <Text style={s.cell}>Days present: {summary.present}</Text>
          <Text style={s.cell}>Absent days: {summary.absent}</Text>
          <Text style={s.cell}>Late: {summary.late}</Text>
          <Text style={s.cell}>Early leave: {summary.earlyLeave}</Text>
          <Text style={s.cell}>Punches: {summary.punches}</Text>
        </View>
        <View style={s.tableHead}>
          <Text style={s.c1}>Date</Text>
          <Text style={s.c2}>First</Text>
          <Text style={s.c3}>Last</Text>
          <Text style={s.c4}>Directions</Text>
          <Text style={s.c5}>Status</Text>
        </View>
        {report.days.map((d) => (
          <View key={d.date} style={s.row} wrap={false}>
            <Text style={s.c1}>{d.date}</Text>
            <Text style={s.c2}>{d.first ?? "-"}</Text>
            <Text style={s.c3}>{d.last ?? "-"}</Text>
            <Text style={s.c4}>{d.directions || "-"}</Text>
            <Text style={s.c5}>
              {d.absent ? "ABSENT" : [d.late ? "LATE" : "", d.earlyLeave ? "EARLY LEAVE" : ""].filter(Boolean).join(", ") || "On time"}
            </Text>
          </View>
        ))}
      </Page>
    </Document>
  );
}
