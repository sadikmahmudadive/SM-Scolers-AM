import { ABSENT_PLACEHOLDERS, SMS_PLACEHOLDERS, SUMMARY_PLACEHOLDERS, findUnknownPlaceholders } from "@hrm/shared";

export type TemplateField =
  | "normalTemplate"
  | "lateTemplate"
  | "earlyLeaveTemplate"
  | "absentTemplate"
  | "summaryTemplate";

const ALLOWED: Record<TemplateField, readonly string[]> = {
  normalTemplate: SMS_PLACEHOLDERS,
  lateTemplate: SMS_PLACEHOLDERS,
  earlyLeaveTemplate: SMS_PLACEHOLDERS,
  absentTemplate: ABSENT_PLACEHOLDERS,
  summaryTemplate: SUMMARY_PLACEHOLDERS,
};

export const SAMPLE_VALUES: Record<string, string> = {
  "{id}": "12",
  "{name}": "Ayesha Rahman",
  "{time}": "08:21 AM",
  "{date}": "16-Oct-2026",
  "{status}": "Check-In",
  "{role}": "student",
  "{start}": "07:45",
  "{end}": "08:15",
  "{present}": "40",
  "{absent}": "5",
  "{late}": "3",
  "{total}": "45",
};

export function allowedPlaceholders(field: TemplateField): readonly string[] {
  return ALLOWED[field];
}

/** Renders a template with sample values; placeholders not allowed for the field are reported and left as-is. */
export function previewTemplate(field: TemplateField, template: string): { text: string; unknown: string[] } {
  const allowed = ALLOWED[field];
  const unknown = [...new Set(findUnknownPlaceholders(template, allowed))];
  const text = template.replace(/\{[^{}]*\}/g, (token) =>
    allowed.includes(token) && token in SAMPLE_VALUES ? (SAMPLE_VALUES[token] as string) : token,
  );
  return { text, unknown };
}
