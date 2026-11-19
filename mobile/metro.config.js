const http = require("node:http");
const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

config.server.enhanceMiddleware = (middleware) => (request, response, next) => {
  const pathname = new URL(request.url || "/", "http://localhost").pathname;
  if (pathname !== "/api" && !pathname.startsWith("/api/")) {
    return middleware(request, response, next);
  }

  const proxy = http.request(
    {
      hostname: "127.0.0.1",
      port: 8000,
      method: request.method,
      path: request.url,
      headers: { ...request.headers, host: "127.0.0.1:8000" },
    },
    (apiResponse) => {
      response.writeHead(apiResponse.statusCode || 502, apiResponse.headers);
      apiResponse.pipe(response);
    }
  );

  proxy.on("error", (error) => {
    console.error("No se pudo reenviar la solicitud a la API:", error.message);
    if (!response.headersSent) {
      response.writeHead(502, { "Content-Type": "application/json" });
    }
    response.end(JSON.stringify({ detail: "No se pudo conectar con el servidor." }));
  });

  request.pipe(proxy);
};

module.exports = config;
