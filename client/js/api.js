// HTTP client for the (temporary) dev game API.
async function request(method, url, body, token = null) {
  const headers = body ? { "Content-Type": "application/json" } : {};
  if (token) headers["X-Player-Token"] = token; // online rooms: who you are
  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof data.detail === "string" ? data.detail : res.statusText);
    err.status = res.status;
    err.key = typeof data.detail === "string" && data.detail.startsWith("error.") ? data.detail : null;
    throw err;
  }
  return data;
}

export const api = {
  createGame: (players, classes) => request("POST", "/api/dev/games", { players, classes }),
  listClasses: () => request("GET", "/api/dev/classes"),
  getView: (gameId, seat) => request("GET", `/api/dev/games/${gameId}/view?seat=${seat}`),
  getVersion: (gameId) => request("GET", `/api/dev/games/${gameId}/version`),
  act: (gameId, action) => request("POST", `/api/dev/games/${gameId}/actions`, action),
  // Online rooms
  hostRoom: (name, classId) => request("POST", "/api/rooms", { name, class_id: classId }),
  joinRoom: (code, name, classId) => request("POST", `/api/rooms/${encodeURIComponent(code)}/join`, { name, class_id: classId }),
  roomView: (code, token) => request("GET", `/api/rooms/${code}`, null, token),
  roomUpdate: (code, token, changes) => request("POST", `/api/rooms/${code}/player`, changes, token),
  roomLeave: (code, token) => request("POST", `/api/rooms/${code}/leave`, {}, token),
  roomStart: (code, token) => request("POST", `/api/rooms/${code}/start`, {}, token),
  roomVersion: (code, token) => request("GET", `/api/rooms/${code}/version`, null, token),
  roomGame: (code, token) => request("GET", `/api/rooms/${code}/game`, null, token),
  roomAct: (code, token, action) => request("POST", `/api/rooms/${code}/actions`, action, token),
};
