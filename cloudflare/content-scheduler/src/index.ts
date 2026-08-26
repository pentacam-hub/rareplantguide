interface Env {
  AGENT_DEPLOY_HOOK_URL: string;
  MANUAL_TRIGGER_TOKEN?: string;
}

async function triggerBuild(env: Env): Promise<Response> {
  if (!env.AGENT_DEPLOY_HOOK_URL) {
    return new Response("AGENT_DEPLOY_HOOK_URL is not configured", { status: 500 });
  }

  const response = await fetch(env.AGENT_DEPLOY_HOOK_URL, { method: "POST" });
  const body = await response.text();

  if (!response.ok) {
    return new Response(`Cloudflare deploy hook failed: ${response.status}\n${body}`, {
      status: 502,
    });
  }

  return new Response(body || "Content-agent build triggered", {
    status: 200,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return Response.json({ ok: true, service: "rareplant-content-scheduler" });
    }

    if (url.pathname !== "/run" || request.method !== "POST") {
      return new Response("Not found", { status: 404 });
    }

    if (env.MANUAL_TRIGGER_TOKEN) {
      const supplied = request.headers.get("authorization") || "";
      if (supplied !== `Bearer ${env.MANUAL_TRIGGER_TOKEN}`) {
        return new Response("Unauthorized", { status: 401 });
      }
    }

    return triggerBuild(env);
  },

  async scheduled(
    controller: ScheduledController,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<void> {
    ctx.waitUntil(
      triggerBuild(env).then(async (response) => {
        if (!response.ok) {
          throw new Error(await response.text());
        }
        console.log(`Content agent triggered by ${controller.cron}`);
      }),
    );
  },
} satisfies ExportedHandler<Env>;
