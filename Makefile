.PHONY: help run start setup setup-check setup-remove run-api run-ui run-falkordb test init-db clean

help:
	@echo "WC Optimizer - Available Commands"
	@echo "=================================="
	@echo "make start         - Full start: build + run + auto-configure MCP"
	@echo "make run           - Start full stack with docker compose"
	@echo "make setup         - Auto-configure Claude Desktop & Cursor IDE"
	@echo "make setup-check   - Check MCP configuration status"
	@echo "make setup-remove  - Remove MCP configuration"
	@echo "make run-api       - Start FastAPI dev server"
	@echo "make run-ui        - Start Streamlit dev server"
	@echo "make run-falkordb  - Start only FalkorDB container"
	@echo "make init-db       - Initialize database schemas"
	@echo "make test          - Run all tests"
	@echo "make expose-mcp    - Expose MCP server via Cloudflare tunnel"
	@echo "make clean         - Stop and clean up containers"

start:
	docker compose up --build -d
	@echo ""
	@echo "Waiting for containers to be healthy..."
	@timeout /t 10 /nobreak >nul 2>&1 || sleep 10
	python scripts/setup_mcp.py
	@echo ""
	@echo "🎉 WC Optimizer is ready!"
	@echo "   Dashboard: http://localhost:8501"
	@echo "   API Docs:  http://localhost:8000/docs"

run:
	docker compose up --build

setup:
	python scripts/setup_mcp.py

setup-check:
	python scripts/setup_mcp.py --check

setup-remove:
	python scripts/setup_mcp.py --uninstall

run-api:
	cd api && uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-ui:
	cd ui && streamlit run app.py --server.port=8501

run-falkordb:
	docker run -d --name falkordb -p 6379:6379 falkordb/falkordb:latest

init-db:
	python scripts/init_db.py

test:
	pytest tests/ -v

expose-mcp:
	@echo "Starting Cloudflare tunnel for MCP server..."
	@echo "Run this in a separate terminal:"
	@echo "cloudflared tunnel --url http://localhost:3001"

clean:
	docker compose down -v
	docker rmi -f wc-optimizer-ui wc-optimizer-api wc-optimizer-mcp-sse 2>/dev/null || true
	@echo "Cleaned up containers and images"
