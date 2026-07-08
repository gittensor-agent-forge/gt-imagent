import { NextResponse } from "next/server";
import { resolvePlaygroundEnvironment } from "@/lib/playground";
import {
  IMAGENT_GENERATION_MODEL_ID,
  IMAGENT_GENERATION_MODEL_OPTION
} from "@/lib/models";
import { resolvePublicSiteUrl } from "@/lib/site";

type VerifyRequest = {
  apiKey?: string;
};

type OpenRouterKeyResponse = {
  data?: {
    label?: string;
    limit?: number | null;
    limit_remaining?: number | null;
    usage?: number | null;
    is_free_tier?: boolean | null;
  };
  error?: {
    message?: string;
    code?: string;
  };
};

type OpenRouterModel = {
  id?: string;
  name?: string;
  description?: string;
  architecture?: {
    output_modalities?: string[];
    modality?: string;
  };
  pricing?: Record<string, string | number | null | undefined> | Array<Record<string, string | number | null | undefined>>;
};

type OpenRouterModelsResponse = {
  data?: OpenRouterModel[];
  error?: {
    message?: string;
    code?: string;
  };
};

const OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key";
const OPENROUTER_IMAGE_MODELS_URL = "https://openrouter.ai/api/v1/images/models";

export async function POST(request: Request) {
  const body = await parseJson<VerifyRequest>(request);
  const publicSiteUrl = resolvePublicSiteUrl();
  const requestedApiKey = String(body.apiKey || "").trim();
  const environment = resolvePlaygroundEnvironment();
  const sharedServerKey = environment.allowServerKeyFallback ? environment.configuredServerApiKey : "";
  const apiKey = requestedApiKey || sharedServerKey;
  const usingServerKey = !requestedApiKey && Boolean(sharedServerKey);

  if (!apiKey) {
    return NextResponse.json({ error: "OpenRouter API key is required." }, { status: 400 });
  }

  const keyResponse = await fetch(OPENROUTER_KEY_URL, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "HTTP-Referer": publicSiteUrl,
      "X-OpenRouter-Title": "Imagent UI"
    },
    cache: "no-store"
  });
  const keyPayload = await parseJson<OpenRouterKeyResponse>(keyResponse);

  if (!keyResponse.ok || keyPayload.error) {
    return NextResponse.json(
      {
        error: keyPayload.error?.message || `OpenRouter key verification failed with HTTP ${keyResponse.status}`,
        code: keyPayload.error?.code || String(keyResponse.status)
      },
      { status: keyResponse.status || 401 }
    );
  }

  const modelsResponse = await fetch(OPENROUTER_IMAGE_MODELS_URL, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "HTTP-Referer": publicSiteUrl,
      "X-OpenRouter-Title": "Imagent UI"
    },
    cache: "no-store"
  });
  const modelsPayload = await parseJson<OpenRouterModelsResponse>(modelsResponse);

  if (!modelsResponse.ok || modelsPayload.error) {
    return NextResponse.json(
      {
        verified: true,
        key: keyPayload.data || null,
        models: [fixedModelOption()],
        usingServerKey,
        warning: modelsPayload.error?.message || `OpenRouter model discovery failed with HTTP ${modelsResponse.status}`
      },
      { status: 200 }
    );
  }

  const fixedModel = (modelsPayload.data || []).find((model) => model.id === IMAGENT_GENERATION_MODEL_ID);
  const models = [fixedModelOption(fixedModel)];

  return NextResponse.json({
    verified: true,
    key: keyPayload.data || null,
    models,
    usingServerKey
  });
}

function fixedModelOption(model?: OpenRouterModel) {
  return {
    id: IMAGENT_GENERATION_MODEL_ID,
    name: String(model?.name || IMAGENT_GENERATION_MODEL_OPTION.name),
    description: String(model?.description || IMAGENT_GENERATION_MODEL_OPTION.description),
    pricing: pricingLabel(model?.pricing) || IMAGENT_GENERATION_MODEL_OPTION.pricing
  };
}

async function parseJson<T>(response: Request | Response): Promise<T> {
  try {
    return (await response.json()) as T;
  } catch {
    return {} as T;
  }
}

function pricingLabel(pricing: OpenRouterModel["pricing"]) {
  if (!pricing || Array.isArray(pricing)) {
    return "OpenRouter pricing";
  }
  const orderedKeys = ["image", "request", "prompt", "completion"];
  const parts = orderedKeys
    .map((key) => {
      const value = Number(pricing[key] || 0);
      return value > 0 ? `${key} ${formatUsd(value)}` : "";
    })
    .filter(Boolean);

  return parts.length ? parts.join(" · ") : "pricing unavailable";
}

function formatUsd(value: number) {
  if (value >= 1) {
    return `$${value.toFixed(2)}`;
  }
  if (value >= 0.01) {
    return `$${value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}`;
  }
  return `$${value.toPrecision(3)}`;
}
