const byId = (id) => document.getElementById(id);
const commands = {
  run: "CMD_RUN",
  step: "CMD_STEP",
  pause: "CMD_PAUSE",
  abort: "CMD_ABORT",
  close: "CMD_CLOSE",
};
const controllers = new Map(),
  leases = new Map(),
  cursors = new Map();
let connected = false,
  busy = false,
  refreshing = false,
  generation = 0,
  socket = null;
let health = {},
  catalog = [],
  executions = [],
  selected = "";
const current = () => byId("context").value;
const identity = (context, id) => JSON.stringify([context, id]);
const selectedRow = () => executions.find((row) => row.id === selected);
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const permitted = (permission) => health.permissions?.includes(permission);

async function api(path, body, key) {
  const options = {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
    headers: {},
  };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  if (key) options.headers["Idempotency-Key"] = key;
  const response = await fetch("/workspace/v1/" + path, options);
  if (!response.ok) throw new Error("Gateway returned " + response.status);
  const data = await response.json();
  if (data.schema !== "openbexi.listener/1")
    throw new Error("Gateway protocol differs");
  return data;
}
const endpoint = (context, resource) =>
  "contexts/" + encodeURIComponent(context) + "/" + resource;
async function authority(context, method, payload, key = crypto.randomUUID()) {
  return (await api(endpoint(context, "authority"), { method, payload }, key))
    .result;
}
function remember(context, receipt) {
  if (!receipt.capability || !receipt.connection_id)
    throw new Error("Controller proof was not delivered");
  controllers.set(identity(context, receipt.id), {
    execution_id: receipt.id,
    expected_epoch: receipt.epoch,
    connection_generation: receipt.connection_generation,
    connection_id: receipt.connection_id,
    capability: receipt.capability,
  });
}
function discard(context) {
  for (const key of controllers.keys())
    if (JSON.parse(key)[0] === context) controllers.delete(key);
  const lease = leases.get(context);
  if (lease) clearTimeout(lease.timer);
  leases.delete(context);
}
function renew(context, lease, receipt) {
  if (
    !Number.isInteger(receipt.lease_seconds) ||
    receipt.lease_seconds < 5 ||
    receipt.lease_seconds > 300 ||
    typeof receipt.heartbeat_nonce !== "string" ||
    !/^[0-9a-f]{64}$/.test(receipt.heartbeat_nonce)
  ) {
    discard(context);
    throw new Error("Controller heartbeat receipt differs");
  }
  lease.timer = setTimeout(
    async () => {
      if (leases.get(context) !== lease) return;
      try {
        const next = await authority(context, "session.heartbeat", {
          connection_id: lease.id,
          heartbeat_nonce: receipt.heartbeat_nonce,
        });
        if (leases.get(context) === lease) renew(context, lease, next);
      } catch {
        if (leases.get(context) === lease) {
          discard(context);
          byId("notice").textContent =
            "Controller connection is unconfirmed. Reconnect explicitly.";
          buttons();
        }
      }
    },
    (receipt.lease_seconds * 1000) / 3,
  );
}
async function session(context) {
  if (leases.has(context)) return leases.get(context).id;
  const opened = await authority(context, "session.open", {});
  const lease = { id: opened.connection_id, timer: null };
  leases.set(context, lease);
  if ("heartbeat_nonce" in opened) renew(context, lease, opened);
  return lease.id;
}
function buttons() {
  const row = selectedRow(),
    context = current(),
    own = row?.owner === health.subject;
  const ownerProof = row && controllers.get(identity(context, row.id));
  const control = connected && !busy && permitted("execution:control");
  const start = control && permitted("execution:start");
  const claim = row?.pending_claim;
  const enabled = {
    reserve: start && catalog.length,
    claim:
      control &&
      permitted("execution:request_control") &&
      row &&
      !own &&
      !claim,
    rebind:
      control &&
      own &&
      !ownerProof &&
      (row?.lifecycle === "RESERVED" ||
        row?.control_state === "HANDOFF_PAUSED" ||
        (health.native_rebind &&
          ["OWNED", "CONTROLLER_DISCONNECTED"].includes(row?.control_state))),
    accept: control && own && ownerProof && claim,
    reject: control && own && ownerProof && claim,
    start:
      start &&
      health.native_launch &&
      own &&
      ownerProof &&
      row.lifecycle === "RESERVED" &&
      row.control_state === "OWNED" &&
      !row.native_start_admitted,
  };
  for (const [id, command] of Object.entries(commands)) {
    enabled[id] =
      control &&
      own &&
      ownerProof &&
      row.lifecycle === "STARTING" &&
      row.native_root_registered !== false &&
      !row.native_root_result &&
      (row.control_state === "OWNED" ||
        (row.control_state === "HANDOFF_PAUSED" && id === "run")) &&
      health.native_commands?.includes(command);
  }
  for (const [id, enabledNow] of Object.entries(enabled))
    byId(id).disabled = !enabledNow;
  byId("context").disabled = busy || !connected;
  byId("refresh").disabled = busy || !connected;
  byId("connection").disabled = busy;
  byId("connection").textContent = connected ? "Disconnect" : "Connect";
}
function render() {
  byId("identity").textContent = health.subject || "";
  const previous = byId("procedures").value;
  byId("procedures").replaceChildren(
    ...catalog.map((p) => new Option(p.procedure_id, p.procedure_id)),
  );
  if (catalog.some((p) => p.procedure_id === previous))
    byId("procedures").value = previous;
  const rows = executions.map((row) => {
    const tr = document.createElement("tr"),
      td = document.createElement("td"),
      choice = document.createElement("button");
    choice.textContent = row.procedure_id;
    choice.setAttribute("aria-pressed", String(row.id === selected));
    choice.dataset.id = row.id;
    choice.onclick = () => {
      selected = row.id;
      render();
    };
    td.append(choice);
    tr.append(td);
    for (const value of [
      row.owner,
      row.control_state,
      row.pending_claim?.requester || "",
      row.native_root_result || "",
    ]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      tr.append(cell);
    }
    return tr;
  });
  byId("executions").replaceChildren(...rows);
  buttons();
}
async function refresh() {
  if (!connected || refreshing || !current()) return;
  const context = current(),
    stamp = generation;
  refreshing = true;
  try {
    const checked = (await api(endpoint(context, "health"))).result;
    const list = (await api(endpoint(context, "executions"))).result.executions;
    let procedures = [];
    try {
      procedures = (await api(endpoint(context, "procedures"))).result
        .procedures;
    } catch (err) {
      if (err.message !== "Gateway returned 404") throw err;
    }
    if (connected && generation === stamp && current() === context) {
      health = checked;
      catalog = procedures;
      executions = list;
      if (!list.some((row) => row.id === selected)) selected = "";
      for (const row of list) {
        const key = identity(context, row.id),
          proof = controllers.get(key);
        if (
          proof &&
          (row.owner !== health.subject ||
            row.epoch !== proof.expected_epoch ||
            row.connection_generation !== proof.connection_generation)
        )
          controllers.delete(key);
      }
      render();
    }
  } finally {
    refreshing = false;
  }
}
function startStream() {
  if (socket) {
    socket.onclose = null;
    socket.close();
    socket = null;
  }
  const context = current(),
    stamp = generation;
  if (!connected || !context) return;
  const ws = new WebSocket(
    "wss://" + location.host + "/workspace/" + endpoint(context, "events"),
    "openbexi.events.v1",
  );
  socket = ws;
  let timer;
  const pull = () => {
    if (ws.readyState === WebSocket.OPEN)
      ws.send(JSON.stringify({ after_sequence: cursors.get(context) || 0 }));
  };
  ws.onopen = pull;
  ws.onmessage = async (message) => {
    if (socket !== ws || stamp !== generation) return;
    const page = JSON.parse(message.data);
    if (
      page.context_id !== context ||
      !Number.isSafeInteger(page.next_sequence) ||
      page.next_sequence < (cursors.get(context) || 0) ||
      !Array.isArray(page.events)
    ) {
      ws.close();
      return;
    }
    const changed = page.next_sequence > (cursors.get(context) || 0);
    cursors.set(context, page.next_sequence);
    byId("stream").textContent = "Live monitoring";
    for (const event of page.events) {
      const li = document.createElement("li");
      li.textContent = event.type;
      li.dataset.sequence = String(event.sequence);
      byId("activity").prepend(li);
      if (byId("activity").children.length > 32)
        byId("activity").lastElementChild.remove();
    }
    if (changed && !busy) {
      try {
        await refresh();
      } catch {
        byId("notice").textContent =
          "Refresh to check the current execution state.";
      }
    }
    timer = setTimeout(pull, page.has_more ? 200 : 1200);
  };
  ws.onclose = () => {
    clearTimeout(timer);
    if (connected && socket === ws && generation === stamp) {
      byId("stream").textContent = "Reconnecting monitoring";
      setTimeout(() => {
        if (connected && socket === ws && generation === stamp) startStream();
      }, 1500);
    }
  };
}
async function connect() {
  const result = await api("contexts");
  byId("context").replaceChildren(
    ...result.contexts.map((c) => new Option(c, c)),
  );
  generation++;
  connected = true;
  await refresh();
  startStream();
}
async function disconnect() {
  connected = false;
  generation++;
  if (socket) {
    socket.close();
    socket = null;
  }
  const closing = [...leases];
  for (const [context] of closing) discard(context);
  controllers.clear();
  health = {};
  catalog = [];
  executions = [];
  selected = "";
  byId("context").replaceChildren();
  byId("activity").replaceChildren();
  byId("stream").textContent = "Disconnected";
  render();
  const results = await Promise.allSettled(
    closing.map(([context, lease]) =>
      authority(context, "session.close", { connection_id: lease.id }),
    ),
  );
  if (results.some((result) => result.status === "rejected"))
    throw new Error("A controller disconnect is unconfirmed");
}
async function launch(context, row, proof) {
  const key = crypto.randomUUID(),
    end = Date.now() + 25000,
    stamp = generation;
  const prepared = await authority(context, "execution.prepare", proof, key);
  if (prepared.preparation_id !== key)
    throw new Error("Native preparation receipt differs");
  while (
    Date.now() < end &&
    connected &&
    generation === stamp &&
    controllers.get(identity(context, row.id)) === proof
  ) {
    const check = await authority(
      context,
      "execution.launch_status",
      proof,
      key,
    );
    if (check.preparation_id !== key || typeof check.ready !== "boolean")
      throw new Error("Native readiness receipt differs");
    if (check.ready) {
      const admitted = await authority(context, "execution.launch", proof, key);
      if (admitted.execution_id !== row.id || admitted.state !== "ADMITTED")
        throw new Error("Native admission is unconfirmed");
      return;
    }
    await delay(250);
  }
  throw new Error("Worker readiness is unconfirmed");
}
async function act(action) {
  const context = current(),
    row = selectedRow(),
    proof = row && controllers.get(identity(context, row.id));
  if (action === "connection") {
    if (connected) await disconnect();
    else await connect();
    return;
  }
  if (action === "refresh") {
    await refresh();
    return;
  }
  if (action === "reserve") {
    const source = catalog.find(
      (p) => p.procedure_id === byId("procedures").value,
    );
    const payload = { connection_id: await session(context) };
    for (const key of [
      "procedure_id",
      "source_revision",
      "source_sha256",
      "runtime_image",
      "driver_binding",
    ])
      payload[key] = source[key];
    const receipt = await authority(context, "execution.reserve", payload);
    remember(context, receipt);
    selected = receipt.id;
  } else if (action === "claim" || action === "rebind") {
    const reply = await authority(context, "execution." + action, {
      execution_id: row.id,
      expected_epoch: row.epoch,
      connection_id: await session(context),
    });
    if (action === "rebind") remember(context, reply);
  } else if (action === "accept" || action === "reject") {
    const reply = await authority(context, "execution.decide", {
      ...proof,
      claim_id: row.pending_claim.id,
      decision: action,
    });
    if (["ACCEPTED", "BLOCKED", "REQUESTED", "PAUSING"].includes(reply.state))
      controllers.delete(identity(context, row.id));
  } else if (action === "start") {
    await launch(context, row, proof);
  } else if (commands[action]) {
    await api(
      endpoint(context, "commands"),
      { ...proof, target_admission_id: null, command: commands[action] },
      crypto.randomUUID(),
    );
  }
  await refresh();
}
async function invoke(action) {
  if (busy || byId(action).disabled) return;
  busy = true;
  buttons();
  byId("notice").textContent = "";
  try {
    await act(action);
  } catch (err) {
    byId("notice").textContent =
      err.message + ". Refresh to check the recorded state.";
  } finally {
    busy = false;
    buttons();
  }
}
for (const id of [
  "connection",
  "refresh",
  "reserve",
  "rebind",
  "claim",
  "accept",
  "reject",
  "start",
  ...Object.keys(commands),
]) {
  byId(id).onclick = () => invoke(id);
}
byId("context").onchange = async () => {
  generation++;
  selected = "";
  health = {};
  catalog = [];
  executions = [];
  byId("activity").replaceChildren();
  render();
  await refresh();
  startStream();
};
buttons();
invoke("connection");
