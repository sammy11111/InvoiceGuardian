import { AppShell } from "@/components/app-shell";
import { getAllScenarioDetails } from "@/lib/data";

export default function Home() {
  const scenarios = getAllScenarioDetails();
  return <AppShell scenarios={scenarios} />;
}
