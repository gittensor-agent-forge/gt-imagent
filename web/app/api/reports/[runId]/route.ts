import { NextResponse } from "next/server";
import { getReport } from "@/lib/reports";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const { runId } = await context.params;
  const report = await getReport(runId);
  if (!report) {
    return NextResponse.json({ error: "report not found" }, { status: 404 });
  }
  return NextResponse.json(report);
}
