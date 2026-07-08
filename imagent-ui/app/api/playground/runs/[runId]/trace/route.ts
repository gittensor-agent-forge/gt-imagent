import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { loadRunManifest, resolveRunDirectory } from "@/lib/playground";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const { runId } = await context.params;
  const manifest = await loadRunManifest(runId);
  if (!manifest?.traceFileName) {
    return NextResponse.json({ error: "run trace not found" }, { status: 404 });
  }

  const artifactPath = path.join(resolveRunDirectory(runId), manifest.traceFileName);
  try {
    const payload = await fs.readFile(artifactPath, "utf8");
    return new NextResponse(payload, {
      headers: {
        "Cache-Control": "no-store",
        "Content-Type": "application/json; charset=utf-8"
      }
    });
  } catch {
    return NextResponse.json({ error: "run trace not found" }, { status: 404 });
  }
}
