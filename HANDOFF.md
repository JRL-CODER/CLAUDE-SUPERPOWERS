# Handoff — Amazon Ads MCP Server

## Objetivo
Tener un servidor MCP custom con 60+ herramientas de Amazon Advertising (SP/SB/SD) corriendo en Render.com y conectado a Claude Desktop en Windows.

## Estado actual

### ✅ Hecho
- Servidor reescrito con la librería oficial `mcp` (NO FastMCP) — resuelve el error "Method Not Found"
- Código en `CLAUDE-SUPERPOWERS/amazon-ads-mcp-server/mcp_server.py` (branch `claude/cool-ritchie-NjvAo`)
- SP-API MCP local funcionando (20 herramientas) — problema de "forbidden" es de permisos en Seller Central (app en modo Sandbox)

### ⏳ Pendiente — lo más urgente
**Subir los 2 archivos a `https://github.com/JRL-CODER/CHE-MATE-ADS-VAULT-MCP`** para que Render redespliegue:

**`requirements.txt`** (reemplazar todo):
```
mcp>=1.0.0
starlette>=0.27.0
requests>=2.31.0
uvicorn>=0.30.0
```

**`mcp_server.py`** — copiar desde `CLAUDE-SUPERPOWERS/amazon-ads-mcp-server/mcp_server.py`

Render redespliegue automático al hacer commit. El endpoint quedará en:
`https://che-mate-ads-vault-mcp.onrender.com/sse`

### Claude Desktop config (Windows)
Ruta: `C:\Users\Julian\AppData\Roaming\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "che-mate-ads-mcp": {
      "command": "C:\\npx.cmd",
      "args": ["-y", "mcp-remote@latest", "https://che-mate-ads-vault-mcp.onrender.com/sse"]
    },
    "amazon-sp-mcp": {
      "command": "node",
      "args": ["C:\\amazon-sp-mcp\\build\\index.js"],
      "env": {
        "LWA_CLIENT_ID": "<tu-client-id>",
        "LWA_CLIENT_SECRET": "<tu-client-secret>",
        "LWA_REFRESH_TOKEN": "<tu-refresh-token>",
        "SELLER_ID": "A21KFRXB7JWEPM",
        "MARKETPLACE_ID": "ATVPDKIKX0DER"
      }
    }
  }
}
```

## Arquitectura del servidor

| Archivo | Descripción |
|---------|-------------|
| `mcp_server.py` | Servidor MCP con Starlette + uvicorn. Rutas: `/sse` y `/messages/` |
| `requirements.txt` | `mcp>=1.0.0`, `starlette`, `requests`, `uvicorn` |
| `render.yaml` | Deploy config para Render.com |

**Variables de entorno en Render** (ya configuradas en el dashboard de Render):
- `REFRESH_TOKEN` — refresh token de Amazon Ads
- `CLIENT_ID` — client ID de la app de Amazon Ads
- `CLIENT_SECRET` — client secret
- `API_REGION` — `na`
- `PORT` — `8000`

## Por qué falló antes / por qué funciona ahora

FastMCP tuvo 3+ cambios de API entre versiones que causaban "Method Not Found":
- v3.4.2: eliminó el param `host`
- v1.0: `run_http_async()` no existe, `run_sse_async()` no acepta `host`/`port`
- El routing SSE de FastMCP no estaba propagando los tool calls correctamente

La solución final usa `mcp.server.Server` + `mcp.server.sse.SseServerTransport` directamente, con handlers explícitos `@server.list_tools()` y `@server.call_tool()`.

## SP-API forbidden — solución pendiente
En Seller Central → Apps → tu app → cambiar de **Sandbox** a **Production** y re-autorizar. Hasta que no esté en Production, todas las llamadas reales devuelven 403.

## Repos relevantes
- Custom Ads MCP: `https://github.com/JRL-CODER/CHE-MATE-ADS-VAULT-MCP`
- Este repo (código local): `https://github.com/JRL-CODER/CLAUDE-SUPERPOWERS` branch `claude/cool-ritchie-NjvAo`
