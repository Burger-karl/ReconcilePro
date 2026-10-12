"use client";

/**
 * Overview (slice F2, pages/dashboard.md): four figures, collections by week, ageing, recent activity.
 * Every number comes from the API already derived (backend D-48); this page only formats and lays out.
 */

import { CircleAlert } from "lucide-react";
import useSWR from "swr";

import { Screen } from "@/components/app-shell/screen";
import { AgeingList } from "@/components/dashboard/ageing-list";
import { CollectionsChart } from "@/components/dashboard/collections-chart";
import { KpiTiles } from "@/components/dashboard/kpi-tiles";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { API, type Schemas } from "@/lib/api";

export default function OverviewPage() {
  // Four independent requests: each section shows its own skeleton and fills in as soon as its data arrives.
  // The summary key is the same one the rail's "Match" badge uses, so SWR sends it only once.
  const summary = useSWR<Schemas["Summary"]>(`${API}/dashboard/summary`);
  const collections = useSWR<Schemas["WeekCollected"][]>(`${API}/dashboard/collections?weeks=8`);
  const ageing = useSWR<Schemas["AgeingBucket"][]>(`${API}/dashboard/ageing`);
  const activity = useSWR<Schemas["AuditEventList"]>(`${API}/audit?limit=8`);

  const failed = [summary, collections, ageing, activity].find((request) => request.error);
  const retry = () => [summary, collections, ageing, activity].forEach((request) => void request.mutate());

  return (
    <Screen title="Overview" description="Where your money is: owed, collected, and what needs you.">
      <div className="flex flex-col gap-4">
        {failed && (
          <Alert variant="destructive">
            <CircleAlert aria-hidden />
            <AlertDescription className="flex flex-wrap items-center justify-between gap-2">
              {failed.error instanceof Error ? failed.error.message : "Some figures couldn't be loaded."}
              <Button size="sm" variant="outline" onClick={retry}>
                Try again
              </Button>
            </AlertDescription>
          </Alert>
        )}
        <KpiTiles summary={summary.data} />
        <div className="grid gap-4 lg:grid-cols-3">
          <CollectionsChart weeks={collections.data} />
          <AgeingList buckets={ageing.data} />
        </div>
        <RecentActivity events={activity.data?.items} />
      </div>
    </Screen>
  );
}
