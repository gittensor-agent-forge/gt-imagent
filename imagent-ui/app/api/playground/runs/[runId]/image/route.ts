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
  if (!manifest) {
    return NextResponse.json({ error: "run image not found" }, { status: 404 });
  }

  const artifactPath = path.join(resolveRunDirectory(runId), manifest.imageFileName);
  try {
    const bytes = await fs.readFile(artifactPath);
    return new NextResponse(bytes, {
      headers: {
        "Cache-Control": "private, max-age=31536000, immutable",
        "Content-Disposition": `inline; filename="${manifest.imageFileName}"`,
        "Content-Type": manifest.imageMediaType
      }
    });
  } catch {
    return NextResponse.json({ error: "run image not found" }, { status: 404 });
  }
}
