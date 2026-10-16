import { seed } from "./seed";

export default async function globalSetup(): Promise<void> {
  await seed();
}
