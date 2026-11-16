// HTTP client for the (temporary) dev game API.
async function request(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof data.detail === "string" ? data.detail : res.statusText);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  createGame: (players) => request("POST", "/api/dev/games", { players }),
  getView: (gameId, seat) => request("GET", `/api/dev/games/${gameId}/view?seat=${seat}`),
  act: (gameId, action) => request("POST", `/api/dev/games/${gameId}/actions`, action),
};
