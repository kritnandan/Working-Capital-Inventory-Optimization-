.PHONY: help run run-api run-ui run-falkordb test init-db clean

help:
	@echo "WC Optimizer - Available Commands"
	@echo "=================================="
	@echo "make run           - Start full stack with docker compose"
	@echo "make run-api       - Start FastAPI dev server"
	@echo "make run-ui        - Start Streamlit dev server"
	@echo "make run-falkordb  - Start only FalkorDB container"
	@echo "make init-db       - Initialize database schemas"
	@echo "make test          - Run all tests"
	@echo "make expose-mcp    - Expose MCP server via Cloudflare tunnel"
	@echo "make clean         - Stop and clean up containers"

run:
	docker compose up --build

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

