"""
Webhook endpoints for external integrations.
"""

from fastapi import APIRouter, Request, Header, HTTPException
from typing import Optional, Dict, Any
import json
from app.services.github_webhooks import github_webhook_handler
from app.core.logging_config import logger

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery")
):
    """
    Handle GitHub webhook events.
    
    Configure this endpoint in your GitHub repository settings:
    - Payload URL: https://your-domain/api/v1/webhooks/github
    - Content type: application/json
    - Secret: Your webhook secret
    - Events: Choose which events to receive
    """
    try:
        # Get raw payload
        payload_bytes = await request.body()
        
        # Verify signature if provided
        if x_hub_signature_256:
            if not github_webhook_handler.verify_signature(payload_bytes, x_hub_signature_256):
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse payload
        try:
            payload = json.loads(payload_bytes)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Log webhook receipt
        logger.info(f"Received GitHub webhook: {x_github_event} (delivery: {x_github_delivery})")
        
        # Process webhook
        result = await github_webhook_handler.handle_webhook(
            event_type=x_github_event,
            payload=payload,
            signature=x_hub_signature_256
        )
        
        return {
            "status": "success",
            "event": x_github_event,
            "delivery_id": x_github_delivery,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing GitHub webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/ping")
async def github_webhook_ping():
    """
    Ping endpoint for GitHub webhook configuration testing.
    """
    return {
        "status": "ok",
        "message": "GitHub webhook endpoint is active"
    }