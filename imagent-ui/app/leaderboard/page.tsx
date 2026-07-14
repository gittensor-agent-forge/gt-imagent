import type { Metadata } from "next";
import { LeaderboardBoard } from "@/app/components/LeaderboardBoard";
import { LandingBackgroundFx } from "@/app/components/LandingBackgroundFx";
import { listLeaderboardEntries } from "@/lib/reports";

export const metadata: Metadata = {
  title: "Leaderboard | Imagent",
  description: "Imagent benchmark history, resolved pull request state, and the current benchmark king.",
  alternates: {
    canonical: "/leaderboard"
  },
  openGraph: {
    title: "Leaderboard | Imagent",
    description: "Imagent benchmark history, resolved pull request state, and the current benchmark king.",
    url: "/leaderboard"
  }
};

export default async function LeaderboardPage() {
  const entries = await listLeaderboardEntries();

  return (
    <div className="imagent-landing leaderboard-live-page">
      <LandingBackgroundFx />
      <LeaderboardBoard entries={entries} />
    </div>
  );
}
