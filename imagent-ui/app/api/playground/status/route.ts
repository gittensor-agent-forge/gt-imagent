import { NextResponse } from "next/server";
import { getPlaygroundRuntimeStatus } from "@/lib/playground";

export async function GET() {
  return NextResponse.json(await getPlaygroundRuntimeStatus(), { status: 200 });
}
