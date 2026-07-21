import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { loadRunManifest, resolveRunDirectory, safeInlineContentType } from "@/lib/playground";

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
  const isSvg =
    manifest.imageMediaType === "image/svg+xml" || manifest.imageFileName.toLowerCase().endsWith(".svg");
  try {
    const bytes = await fs.readFile(artifactPath);
    return new NextResponse(bytes, {
      headers: {
        "Cache-Control": "private, max-age=31536000, immutable",
        // Raster images render inline; svg is downgraded to a neutral type and
        // forced to download so it cannot execute script in our origin.
        "Content-Disposition": `${isSvg ? "attachment" : "inline"}; filename="${manifest.imageFileName}"`,
        "Content-Type": safeInlineContentType(manifest.imageMediaType, manifest.imageFileName),
        "X-Content-Type-Options": "nosniff"
      }
    });
  } catch {
    return NextResponse.json({ error: "run image not found" }, { status: 404 });
  }
}
