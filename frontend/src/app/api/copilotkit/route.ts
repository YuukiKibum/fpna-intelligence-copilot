const BACKEND_COPILOTKIT_URL =
  process.env.BACKEND_COPILOTKIT_URL ?? "http://127.0.0.1:8000/copilotkit";

async function proxyToBackend(req: Request) {
  const body = await req.text();

  const upstream = await fetch(BACKEND_COPILOTKIT_URL, {
    method: req.method,
    headers: {
      "content-type": req.headers.get("content-type") ?? "application/json",
      accept: req.headers.get("accept") ?? "text/event-stream",
    },
    body,
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type":
        upstream.headers.get("content-type") ?? "text/event-stream",
      "cache-control": "no-cache",
    },
  });
}

export async function POST(req: Request) {
  return proxyToBackend(req);
}