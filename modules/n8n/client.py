"""
N8N workflow automation client.

Provides async client for interacting with the N8N REST API
for workflow management and execution.
"""

from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Callable

import aiohttp

from modules.logging_config import get_logger

logger = get_logger(__name__)


class N8NClient:
    """
    N8N API client for workflow automation.

    Provides methods for creating, managing, and executing N8N workflows.
    Supports webhook triggers for AI Beast integration.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:5678",
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize N8N client.

        Args:
            base_url: N8N server URL
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    @property
    def _headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key
        return headers

    async def __aenter__(self) -> N8NClient:
        """Enter async context."""
        self._session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers=self._headers,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self._session:
            await self._session.close()
            self._session = None

    async def _ensure_session(self):
        """Ensure session is available."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=self._headers,
            )

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Make HTTP request to N8N API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request args

        Returns:
            JSON response or error dict
        """
        await self._ensure_session()

        url = f"{self.base_url}{endpoint}"

        try:
            async with self._session.request(method, url, **kwargs) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    logger.warning(
                        "n8n_request_failed",
                        status=resp.status,
                        endpoint=endpoint,
                        error=error_text[:200],
                    )
                    return {
                        "ok": False,
                        "error": f"HTTP {resp.status}: {error_text[:200]}",
                    }
        except asyncio.TimeoutError:
            logger.error("n8n_request_timeout", endpoint=endpoint)
            return {"ok": False, "error": "Request timeout"}
        except aiohttp.ClientError as e:
            logger.error("n8n_client_error", endpoint=endpoint, error=str(e))
            return {"ok": False, "error": str(e)}
        except Exception as e:
            logger.exception("n8n_request_error", endpoint=endpoint)
            return {"ok": False, "error": str(e)}

    # -------------------------------------------------------------------------
    # Workflow Management
    # -------------------------------------------------------------------------

    async def list_workflows(self) -> list[dict]:
        """
        List all workflows.

        Returns:
            List of workflow dictionaries
        """
        result = await self._request("GET", "/rest/workflows")
        if isinstance(result, dict) and "data" in result:
            return result["data"]
        return []

    async def get_workflow(self, workflow_id: str) -> dict | None:
        """
        Get workflow by ID.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow dict or None if not found
        """
        result = await self._request("GET", f"/rest/workflows/{workflow_id}")
        if result.get("ok") is False:
            return None
        return result

    async def create_workflow(self, workflow: dict) -> dict:
        """
        Create a new workflow.

        Args:
            workflow: Workflow definition

        Returns:
            Created workflow or error dict
        """
        result = await self._request("POST", "/rest/workflows", json=workflow)
        logger.info(
            "n8n_workflow_created",
            workflow_name=workflow.get("name", "unknown"),
            success=result.get("ok") is not False,
        )
        return result

    async def update_workflow(self, workflow_id: str, workflow: dict) -> dict:
        """
        Update an existing workflow.

        Args:
            workflow_id: Workflow ID
            workflow: Updated workflow definition

        Returns:
            Updated workflow or error dict
        """
        result = await self._request(
            "PATCH",
            f"/rest/workflows/{workflow_id}",
            json=workflow,
        )
        logger.info(
            "n8n_workflow_updated",
            workflow_id=workflow_id,
            success=result.get("ok") is not False,
        )
        return result

    async def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if deleted successfully
        """
        result = await self._request("DELETE", f"/rest/workflows/{workflow_id}")
        success = result.get("ok") is not False
        logger.info(
            "n8n_workflow_deleted",
            workflow_id=workflow_id,
            success=success,
        )
        return success

    async def activate_workflow(self, workflow_id: str) -> dict:
        """
        Activate a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Result dict
        """
        result = await self._request("POST", f"/rest/workflows/{workflow_id}/activate")
        logger.info(
            "n8n_workflow_activated",
            workflow_id=workflow_id,
            success=result.get("ok") is not False,
        )
        return result

    async def deactivate_workflow(self, workflow_id: str) -> dict:
        """
        Deactivate a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Result dict
        """
        result = await self._request(
            "POST",
            f"/rest/workflows/{workflow_id}/deactivate",
        )
        logger.info(
            "n8n_workflow_deactivated",
            workflow_id=workflow_id,
            success=result.get("ok") is not False,
        )
        return result

    # -------------------------------------------------------------------------
    # Webhook Execution
    # -------------------------------------------------------------------------

    async def execute_webhook(
        self,
        webhook_path: str,
        data: dict[str, Any] | None = None,
        method: str = "POST",
    ) -> dict:
        """
        Execute a workflow via webhook.

        Args:
            webhook_path: Webhook path (without /webhook/ prefix)
            data: Data to send to webhook
            method: HTTP method (POST, GET)

        Returns:
            Webhook response
        """
        await self._ensure_session()

        url = f"{self.base_url}/webhook/{webhook_path}"
        kwargs = {"json": data} if method == "POST" and data else {}

        try:
            async with self._session.request(method, url, **kwargs) as resp:
                logger.info(
                    "n8n_webhook_executed",
                    webhook=webhook_path,
                    status=resp.status,
                )
                if resp.status == 200:
                    content_type = resp.headers.get("content-type", "")
                    if "json" in content_type:
                        return await resp.json()
                    return {"ok": True, "response": await resp.text()}
                return {"ok": False, "error": f"HTTP {resp.status}"}
        except Exception as e:
            logger.error(
                "n8n_webhook_failed",
                webhook=webhook_path,
                error=str(e),
            )
            return {"ok": False, "error": str(e)}

    async def trigger_test_webhook(
        self,
        webhook_path: str,
        data: dict[str, Any] | None = None,
    ) -> dict:
        """
        Trigger test webhook execution.

        Args:
            webhook_path: Webhook path
            data: Test data

        Returns:
            Test execution result
        """
        url = f"{self.base_url}/webhook-test/{webhook_path}"
        await self._ensure_session()

        try:
            async with self._session.post(url, json=data or {}) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"ok": False, "error": f"HTTP {resp.status}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # -------------------------------------------------------------------------
    # Execution Management
    # -------------------------------------------------------------------------

    async def list_executions(
        self,
        workflow_id: str | None = None,
        limit: int = 20,
        status: str | None = None,
    ) -> list[dict]:
        """
        List workflow executions.

        Args:
            workflow_id: Filter by workflow ID
            limit: Maximum executions to return
            status: Filter by status (success, error, waiting)

        Returns:
            List of executions
        """
        params = {"limit": limit}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status:
            params["status"] = status

        result = await self._request("GET", "/rest/executions", params=params)
        if isinstance(result, dict) and "data" in result:
            return result["data"]
        return []

    async def get_execution(self, execution_id: str) -> dict | None:
        """
        Get execution details.

        Args:
            execution_id: Execution ID

        Returns:
            Execution dict or None
        """
        result = await self._request("GET", f"/rest/executions/{execution_id}")
        if result.get("ok") is False:
            return None
        return result

    # -------------------------------------------------------------------------
    # Credentials Management
    # -------------------------------------------------------------------------

    async def list_credentials(self) -> list[dict]:
        """
        List all credentials (without sensitive data).

        Returns:
            List of credentials
        """
        result = await self._request("GET", "/rest/credentials")
        if isinstance(result, dict) and "data" in result:
            return result["data"]
        return []

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    async def health_check(self) -> bool:
        """
        Check if N8N is healthy and reachable.

        Returns:
            True if healthy
        """
        await self._ensure_session()

        try:
            async with self._session.get(f"{self.base_url}/healthz") as resp:
                return resp.status == 200
        except Exception:
            return False


# -----------------------------------------------------------------------------
# Pre-built Workflow Templates
# -----------------------------------------------------------------------------

WORKFLOW_TEMPLATES = {
    "model_download_notify": {
        "name": "Model Download Notification",
        "active": False,
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300],
                "parameters": {
                    "path": "model-download",
                    "httpMethod": "POST",
                },
            },
            {
                "id": "2",
                "name": "Send Notification",
                "type": "n8n-nodes-base.noOp",
                "typeVersion": 1,
                "position": [450, 300],
                "parameters": {},
            },
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Send Notification", "type": "main", "index": 0}]]
            }
        },
    },
    "rag_ingest_pipeline": {
        "name": "RAG Document Ingestion",
        "active": False,
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300],
                "parameters": {
                    "path": "rag-ingest",
                    "httpMethod": "POST",
                },
            },
            {
                "id": "2",
                "name": "Execute Command",
                "type": "n8n-nodes-base.executeCommand",
                "typeVersion": 1,
                "position": [450, 300],
                "parameters": {
                    "command": "./bin/beast rag ingest --dir={{ $json.directory }}",
                },
            },
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Execute Command", "type": "main", "index": 0}]]
            }
        },
    },
    "service_health_check": {
        "name": "Service Health Check",
        "active": False,
        "nodes": [
            {
                "id": "1",
                "name": "Schedule Trigger",
                "type": "n8n-nodes-base.scheduleTrigger",
                "typeVersion": 1,
                "position": [250, 300],
                "parameters": {
                    "rule": {"interval": [{"field": "minutes", "minutesInterval": 5}]},
                },
            },
            {
                "id": "2",
                "name": "HTTP Request",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "position": [450, 300],
                "parameters": {
                    "url": "http://host.docker.internal:8787/api/health",
                    "method": "GET",
                },
            },
        ],
        "connections": {
            "Schedule Trigger": {
                "main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]
            }
        },
    },
}


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


async def create_client_from_env() -> N8NClient:
    """
    Create N8N client from environment variables.

    Reads:
        - N8N_BASE_URL or PORT_N8N
        - N8N_API_KEY

    Returns:
        Configured N8NClient
    """
    import os

    port = os.getenv("PORT_N8N", "5678")
    base_url = os.getenv("N8N_BASE_URL", f"http://127.0.0.1:{port}")
    api_key = os.getenv("N8N_API_KEY")

    return N8NClient(base_url=base_url, api_key=api_key)
