/** Poll url until it answers with a non-5xx status, or throw after timeoutMs. */
export async function waitForStack(
  url: string = process.env.BASE_URL ?? 'http://localhost:3000',
  timeoutMs = 60_000,
  intervalMs = 500,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let last = 'no response';
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
      if (res.status < 500) return;
      last = `HTTP ${res.status}`;
    } catch (e) {
      last = (e as Error).message;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Timed out after ${timeoutMs}ms waiting for ${url} (${last})`);
}

if (require.main === module) {
  waitForStack(process.argv[2], Number(process.argv[3] ?? 60_000) || 60_000).then(
    () => process.exit(0),
    (e) => {
      console.error(String(e.message ?? e));
      process.exit(1);
    },
  );
}
