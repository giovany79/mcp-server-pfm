# mcp-server-pfm

MCP server for my personal finances

# Definicion

**MCP:** Model Context Protocolo

# Setup

1.Configure python environment

```shell
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2.Install MCP server

```shell
pip install "mcp[cli]"
```

3.Install UV server

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

4.Run server

```shell
mcp dev server.py 
```

5.Run inspector

```shell
npx @modelcontextprotocol/inspector mcp run server.py
```

6.Actualizar dependencias

```
pip install --upgrade pip && pip install -r requirements.txt
```

7.Run client

```shell
python client.py
```
