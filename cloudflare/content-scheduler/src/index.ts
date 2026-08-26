interface Env {
  CONTENT_AGENT_DEPLOY_HOOK_URL: string;
  PROMO_AGENT_DEPLOY_HOOK_URL: string;
  MANUAL_TRIGGER_TOKEN?: string;
}

type AgentKind = "content" | "promo";

function hookFor(kind: AgentKind, env: Env): string {
  return kind === "content"
    ? env.CONTENT_AGENT_DEPLOY_HOOK_URL
    : env.PROMO_AGENT_DEPLOY_HOOK_URL;
}

async function triggerBuild(kind: AgentKind, env: Env): Promise<Response> {
  const hookUrl = hookFor(kind, env);
  if (!hookUrl) {
    return new Response(`${kind} deploy hook is not configured`, { status: 500 });
  }

  const response = await fetch(hookUrl, { method: "POST" });
  const body = await response.text();

  if (!response.ok) {
    return new Response(`Cloudflare ${kind} deploy hook failed: ${response.status}\n${body}`, {
      status: 502,
    });
  }

  return new Response(body || `${kind} agent build triggered`, {
    status: 200,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function kindForCron(cron: string): AgentKind {
  if (cron === "30 19 * * 1,4") return "content";
  return "promo";
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return Response.json({ ok: true, service: "rareplant-content-scheduler" });
    }

    if (request.method !== "POST") {
      return new Response("Not found", { status: 404 });
    }

    let kind: AgentKind;
    if (url.pathname === "/run/content") kind = "content";
    else if (url.pathname === "/run/promo") kind = "promo";
    else return new Response("Not found", { status: 404 });

    if (env.MANUAL_TRIGGER_TOKEN) {
      const supplied = request.headers.get("authorization") || "";
      if (supplied !== `Bearer ${env.MANUAL_TRIGGER_TOKEN}`) {
        return new Response("Unauthorized", { status: 401 });
      }
    }

    return triggerBuild(kind, env);
  },

  async scheduled(
    controller: ScheduledController,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<void> {
    const kind = kindForCron(controller.cron);
    ctx.waitUntil(
      triggerBuild(kind, env).then(async (response) => {
        if (!response.ok) throw new Error(await response.text());
        console.log(`${kind} agent triggered by ${controller.cron}`);
      }),
    );
  },
} satisfies ExportedHandler<Env>;
