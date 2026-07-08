import { GenerationChat } from "@/app/components/GenerationChat";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Generation | Imagent",
  description: "Test the Imagent reference agent with Google Gemini 3.1 Flash Image through OpenRouter.",
  alternates: {
    canonical: "/generation"
  },
  openGraph: {
    title: "Generation | Imagent",
    description: "Test the Imagent reference agent with Google Gemini 3.1 Flash Image through OpenRouter.",
    url: "/generation"
  }
};

export default function GenerationPage() {
  return <GenerationChat />;
}
