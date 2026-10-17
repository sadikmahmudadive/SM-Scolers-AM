"use client";

import { RouteError } from "@/components/route-error";

// Error boundary for this role group: one failed query shows a message with a retry
// instead of blanking the whole page.
export default function RoleGroupError(props: { error: Error & { digest?: string }; reset: () => void }) {
  return <RouteError {...props} />;
}
