const fs = require("node:fs"),
  path = require("node:path"),
  crypto = require("node:crypto");
const playwright = process.env.PLAYWRIGHT_MODULE || "playwright-core";
const { chromium } = require(playwright);
const [profiles, destination] = process.argv.slice(2);
if (!profiles || !destination)
  throw Error(
    "Supply the private certificate profile directory and a new evidence directory",
  );
const root = path.resolve(profiles),
  output = path.resolve(destination);
fs.mkdirSync(output, { recursive: false });
const origin = JSON.parse(
    fs.readFileSync(path.join(root, "alice", "connection.json")),
  ).url,
  clients = {},
  sessions = [],
  observations = [];
const report = {
  passed: false,
  origin,
  browser: null,
  identities: [],
  observations,
};
const save = () =>
  fs.writeFileSync(
    path.join(output, "browser-result.json"),
    JSON.stringify(report, null, 2) + "\n",
  );
const mark = (name, data = {}) => {
  observations.push({ name, time: new Date().toISOString(), ...data });
  save();
  console.log(name);
};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const waitFor = async (cb, why, seconds = 30) => {
  const until = Date.now() + seconds * 1000;
  while (Date.now() < until) {
    if (await cb()) return;
    await wait(120);
  }
  throw Error("Timed out: " + why);
};
async function open(browser, role) {
  const d = path.join(root, role);
  const context = await browser.newContext({
    viewport: { width: 1170, height: 850 },
    clientCertificates: [
      {
        origin,
        certPath: path.join(d, "tls.pem"),
        keyPath: path.join(d, "tls.key"),
      },
    ],
  });
  sessions.push(context);
  const p = await context.newPage(),
    stats = {
      websockets: [],
      pages: 0,
      types: new Set(),
      cursors: [],
      errors: [],
    };
  p.on("pageerror", (e) => stats.errors.push(e.message.slice(0, 160)));
  p.on("websocket", (w) => {
    stats.websockets.push(w.url());
    w.on("framereceived", (f) => {
      try {
        const j = JSON.parse(f.payload);
        if (j.context_id === "A") {
          stats.pages++;
          stats.cursors.push([j.after_sequence, j.next_sequence]);
          for (const e of j.events) stats.types.add(e.type);
        }
      } catch {}
    });
  });
  await p.goto(origin + "/workspace/", {
    waitUntil: "domcontentloaded",
    timeout: 15000,
  });
  await waitFor(
    async () =>
      (await p.locator("#identity").textContent()) === role && stats.pages > 0,
    role + " authenticated WS",
    20,
  );
  clients[role] = { context, p, stats };
  report.identities.push(role);
  return p;
}
const cell = async (p, col) =>
  await p
    .locator("#executions tr")
    .first()
    .locator("td")
    .nth(col)
    .textContent();
async function choose(p) {
  await p.locator("#executions button").first().click();
}
async function click(p, id) {
  await p.locator("#" + id).click({ timeout: 15000 });
}
async function getFresh(p) {
  await click(p, "refresh");
  await waitFor(
    async () => await p.locator("#refresh").isEnabled(),
    "refresh finished",
    6,
  );
}
async function take(p, name) {
  await p.screenshot({ path: path.join(output, name + ".png") });
}
async function forbidden(p, method, payload) {
  return await p.evaluate(
    async ({ method, payload }) =>
      (
        await fetch("/workspace/v1/contexts/A/authority", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({ method, payload }),
        })
      ).status,
    { method, payload },
  );
}
const certFingerprint = (role) =>
  new crypto.X509Certificate(fs.readFileSync(path.join(root, role, "tls.pem")))
    .fingerprint256;
(async () => {
  const executable = chromium.executablePath();
  report.chromium_sha256 = crypto
    .createHash("sha256")
    .update(fs.readFileSync(executable))
    .digest("hex");
  report.playwright = require(playwright + "/package.json").version;
  if (report.playwright !== "1.65.0")
    throw Error("Expected pinned playwright-core 1.65.0");
  const browser = await chromium.launch({
    executablePath: executable,
    headless: true,
  });
  try {
    report.browser = browser.version();
    if (report.browser !== "158.0.8127.18")
      throw Error("Pinned Chromium version differs");
    const alice = await open(browser, "alice"),
      bob = await open(browser, "bob"),
      third = await open(browser, "observer");
    const observers = Array.from(
      { length: 20 },
      (_, i) => "watch-" + String(i + 1).padStart(2, "0"),
    );
    for (let i = 0; i < observers.length; i += 3)
      await Promise.all(observers.slice(i, i + 3).map((n) => open(browser, n)));
    if (new Set(report.identities.map(certFingerprint)).size !== 23)
      throw Error("Certificate identities not distinct");
    mark("23 authenticated browser identities and real WSS connections", {
      count: report.identities.length,
    });
    for (let i = 0; i < observers.length; i += 4)
      await Promise.all(
        observers.slice(i, i + 4).map(async (role) => {
          const p = clients[role].p;
          if (
            (await p.locator("#reserve").isEnabled()) ||
            (await forbidden(p, "session.open", {})) !== 403
          )
            throw Error("Observer mutation policy " + role);
        }),
      );
    mark("20 observer attempts denied by authority");
    let old;
    const reserveResponse = alice
      .waitForResponse(
        (r) => r.request().postDataJSON?.()?.method === "execution.reserve",
      )
      .catch(() => null);
    await click(alice, "reserve");
    const res = await reserveResponse;
    if (!res || res.status() !== 200)
      throw Error("Reservation response missing");
    const rr = (await res.json()).result;
    old = {
      execution_id: rr.id,
      expected_epoch: rr.epoch,
      connection_generation: rr.connection_generation,
      connection_id: rr.connection_id,
      capability: rr.capability,
    };
    report.execution_id = rr.id;
    await waitFor(
      async () => (await alice.locator("#executions button").count()) === 1,
      "reservation row",
    );
    await choose(alice);
    await waitFor(
      async () => clients.bob.stats.types.has("EXECUTION_RESERVED"),
      "observer event replay",
    );
    await getFresh(bob);
    await choose(bob);
    await click(bob, "claim");
    await waitFor(
      async () => await alice.locator("#accept").isEnabled(),
      "A can decide",
    );
    await click(alice, "accept");
    await waitFor(async () => (await cell(bob, 1)) === "bob", "B visibly owns");
    await click(bob, "rebind");
    await waitFor(
      async () => await bob.locator("#start").isEnabled(),
      "B got explicit control",
    );
    if ((await forbidden(alice, "execution.prepare", old)) !== 403)
      throw Error("Previous controller not fenced");
    old = null;
    mark("A to B ownership, prior A proof denied");
    await getFresh(alice);
    await choose(alice);
    await click(alice, "claim");
    await waitFor(
      async () => await bob.locator("#accept").isEnabled(),
      "B can decide",
    );
    await click(bob, "accept");
    await waitFor(
      async () => (await cell(alice, 1)) === "alice",
      "A visibly owns",
    );
    await click(alice, "rebind");
    await waitFor(
      async () => await alice.locator("#start").isEnabled(),
      "A reacquired explicitly",
    );
    mark("B to A ownership with explicit rebind");
    await getFresh(third);
    await choose(third);
    await take(third, "browser-observer");
    await click(third, "connection");
    await waitFor(
      async () =>
        (await third.locator("#connection").textContent()) === "Connect",
      "observer disconnect",
    );
    await click(third, "connection");
    await waitFor(
      async () =>
        (await third.locator("#identity").textContent()) === "observer" &&
        clients.observer.stats.websockets.length >= 2,
      "observer reconnect",
    );
    await waitFor(
      async () => clients.observer.stats.cursors.at(-1)[0] > 0,
      "read-only cursor resumes",
    );
    mark("Observer reconnected with a nonzero replay cursor");
    await click(alice, "start");
    await waitFor(
      async () => await alice.locator("#run").isEnabled(),
      "native root registered",
      40,
    );
    mark("Browser explicitly started a paused native root");
    await take(alice, "browser-ready");
    await click(alice, "run");
    await waitFor(
      async () => (await cell(alice, 4)) === "FINISHED",
      "browser reported native result",
      40,
    );
    await take(alice, "browser-finished");
    await waitFor(
      async () =>
        (
          await Promise.all(
            observers.map(
              async (n) =>
                (await clients[n].p.locator("#executions tr").count()) > 0 &&
                (await cell(clients[n].p, 4)) === "FINISHED",
            ),
          )
        ).every(Boolean),
      "20 observers saw native result",
      30,
    );
    if (
      (await alice.locator("#run").isEnabled()) ||
      (await bob.locator("#run").isEnabled())
    )
      throw Error("Terminal commands still enabled");
    mark("Native FINISHED visible for owner and 20 observers");
    await click(alice, "connection");
    await waitFor(
      async () =>
        (await alice.locator("#connection").textContent()) === "Connect",
      "A disconnected",
    );
    await click(alice, "connection");
    await waitFor(
      async () => (await alice.locator("#executions button").count()) === 1,
      "A reconnect read",
    );
    await choose(alice);
    if (await alice.locator("#run").isEnabled())
      throw Error("Unexpected resumed control");
    mark("Controller reconnect remained read-only");
    report.passed = true;
  } catch (e) {
    report.error = e.message;
    console.error(e.message);
    process.exitCode = 1;
  } finally {
    report.readers = Object.fromEntries(
      Object.entries(clients).map(([role, { stats }]) => [
        role,
        {
          count: stats.websockets.length,
          pages: stats.pages,
          types: [...stats.types],
          last: stats.cursors.at(-1),
          errors: stats.errors,
        },
      ]),
    );
    await Promise.allSettled(sessions.map((c) => c.close()));
    await browser.close();
    save();
  }
})().catch((e) => {
  report.error = e.message;
  save();
  console.error(e.message);
  process.exitCode = 1;
});
