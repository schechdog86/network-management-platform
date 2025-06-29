"""
GitHub webhook handler for real-time repository events.
"""

import hashlib
import hmac
import json
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from fastapi import HTTPException
from app.core.config import settings
from app.core.logging_config import logger
from app.services.websocket_service import websocket_manager
from app.db.session import AsyncSessionLocal
from app.models.notification import Notification, NotificationType
from sqlalchemy.ext.asyncio import AsyncSession


class GitHubWebhookHandler:
    """Handler for GitHub webhook events"""
    
    def __init__(self):
        self.webhook_secret = settings.GITHUB_WEBHOOK_SECRET if hasattr(settings, 'GITHUB_WEBHOOK_SECRET') else ""
        self.event_handlers: Dict[str, Callable] = {
            "push": self._handle_push,
            "pull_request": self._handle_pull_request,
            "issues": self._handle_issues,
            "workflow_run": self._handle_workflow_run,
            "deployment": self._handle_deployment,
            "deployment_status": self._handle_deployment_status,
            "release": self._handle_release,
            "check_suite": self._handle_check_suite,
            "check_run": self._handle_check_run,
        }
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        if not self.webhook_secret:
            logger.warning("GitHub webhook secret not configured")
            return True  # Allow in development
        
        expected_signature = "sha256=" + hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    async def handle_webhook(self, event_type: str, payload: Dict[str, Any], signature: Optional[str] = None) -> Dict[str, Any]:
        """Handle incoming webhook event"""
        logger.info(f"Received GitHub webhook event: {event_type}")
        
        # Get handler for event type
        handler = self.event_handlers.get(event_type)
        if not handler:
            logger.warning(f"No handler for GitHub event type: {event_type}")
            return {"status": "ignored", "reason": "unsupported event type"}
        
        try:
            # Process event
            result = await handler(payload)
            
            # Broadcast update via WebSocket
            await self._broadcast_update(event_type, payload)
            
            return {"status": "processed", "event": event_type, "result": result}
            
        except Exception as e:
            logger.error(f"Error processing GitHub webhook: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def _handle_push(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle push event"""
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
        repository = payload.get("repository", {})
        pusher = payload.get("pusher", {})
        commits = payload.get("commits", [])
        
        # Create notification
        message = f"{pusher.get('name', 'Unknown')} pushed {len(commits)} commit(s) to {branch}"
        await self._create_notification(
            title="New Push to Repository",
            message=message,
            notification_type=NotificationType.INFO,
            metadata={
                "branch": branch,
                "commits": len(commits),
                "repository": repository.get("full_name"),
                "pusher": pusher.get("name"),
            }
        )
        
        return {
            "branch": branch,
            "commits": len(commits),
            "repository": repository.get("full_name"),
        }
    
    async def _handle_pull_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle pull request event"""
        action = payload.get("action")
        pr = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        
        # Create notification based on action
        title = f"Pull Request {action.title()}"
        message = f"PR #{pr.get('number')}: {pr.get('title')} - {action} by {pr.get('user', {}).get('login', 'Unknown')}"
        
        notification_type = NotificationType.INFO
        if action == "closed" and pr.get("merged"):
            notification_type = NotificationType.SUCCESS
            title = "Pull Request Merged"
        elif action == "opened":
            notification_type = NotificationType.INFO
        
        await self._create_notification(
            title=title,
            message=message,
            notification_type=notification_type,
            metadata={
                "pr_number": pr.get("number"),
                "action": action,
                "repository": repository.get("full_name"),
                "author": pr.get("user", {}).get("login"),
            }
        )
        
        return {
            "action": action,
            "pr_number": pr.get("number"),
            "title": pr.get("title"),
        }
    
    async def _handle_issues(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle issues event"""
        action = payload.get("action")
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        
        # Create notification
        title = f"Issue {action.title()}"
        message = f"Issue #{issue.get('number')}: {issue.get('title')} - {action}"
        
        notification_type = NotificationType.INFO
        if action == "closed":
            notification_type = NotificationType.SUCCESS
        elif action == "opened" and "bug" in [label.get("name", "").lower() for label in issue.get("labels", [])]:
            notification_type = NotificationType.WARNING
        
        await self._create_notification(
            title=title,
            message=message,
            notification_type=notification_type,
            metadata={
                "issue_number": issue.get("number"),
                "action": action,
                "repository": repository.get("full_name"),
                "labels": [label.get("name") for label in issue.get("labels", [])],
            }
        )
        
        return {
            "action": action,
            "issue_number": issue.get("number"),
            "title": issue.get("title"),
        }
    
    async def _handle_workflow_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle workflow run event"""
        action = payload.get("action")
        workflow_run = payload.get("workflow_run", {})
        repository = payload.get("repository", {})
        
        if action == "completed":
            conclusion = workflow_run.get("conclusion")
            status = workflow_run.get("status")
            
            # Create notification based on conclusion
            if conclusion == "success":
                notification_type = NotificationType.SUCCESS
                title = "Workflow Succeeded"
            elif conclusion == "failure":
                notification_type = NotificationType.ERROR
                title = "Workflow Failed"
            else:
                notification_type = NotificationType.WARNING
                title = f"Workflow {conclusion.title() if conclusion else 'Completed'}"
            
            message = f"{workflow_run.get('name')} #{workflow_run.get('run_number')} - {conclusion or status}"
            
            await self._create_notification(
                title=title,
                message=message,
                notification_type=notification_type,
                metadata={
                    "workflow_name": workflow_run.get("name"),
                    "run_number": workflow_run.get("run_number"),
                    "conclusion": conclusion,
                    "repository": repository.get("full_name"),
                }
            )
        
        return {
            "action": action,
            "workflow": workflow_run.get("name"),
            "conclusion": workflow_run.get("conclusion"),
        }
    
    async def _handle_deployment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle deployment event"""
        deployment = payload.get("deployment", {})
        repository = payload.get("repository", {})
        
        environment = deployment.get("environment")
        ref = deployment.get("ref")
        
        await self._create_notification(
            title=f"Deployment to {environment}",
            message=f"Deploying {ref} to {environment}",
            notification_type=NotificationType.INFO,
            metadata={
                "environment": environment,
                "ref": ref,
                "repository": repository.get("full_name"),
                "deployment_id": deployment.get("id"),
            }
        )
        
        return {
            "environment": environment,
            "ref": ref,
        }
    
    async def _handle_deployment_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle deployment status event"""
        deployment_status = payload.get("deployment_status", {})
        deployment = payload.get("deployment", {})
        repository = payload.get("repository", {})
        
        state = deployment_status.get("state")
        environment = deployment.get("environment")
        
        # Determine notification type based on state
        if state == "success":
            notification_type = NotificationType.SUCCESS
            title = f"Deployment to {environment} Succeeded"
        elif state == "failure" or state == "error":
            notification_type = NotificationType.ERROR
            title = f"Deployment to {environment} Failed"
        else:
            notification_type = NotificationType.INFO
            title = f"Deployment to {environment} - {state}"
        
        await self._create_notification(
            title=title,
            message=deployment_status.get("description", f"Deployment state: {state}"),
            notification_type=notification_type,
            metadata={
                "environment": environment,
                "state": state,
                "repository": repository.get("full_name"),
            }
        )
        
        return {
            "environment": environment,
            "state": state,
        }
    
    async def _handle_release(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle release event"""
        action = payload.get("action")
        release = payload.get("release", {})
        repository = payload.get("repository", {})
        
        if action == "published":
            await self._create_notification(
                title="New Release Published",
                message=f"{release.get('name') or release.get('tag_name')} - {release.get('author', {}).get('login', 'Unknown')}",
                notification_type=NotificationType.SUCCESS,
                metadata={
                    "tag": release.get("tag_name"),
                    "name": release.get("name"),
                    "repository": repository.get("full_name"),
                    "prerelease": release.get("prerelease", False),
                }
            )
        
        return {
            "action": action,
            "tag": release.get("tag_name"),
            "name": release.get("name"),
        }
    
    async def _handle_check_suite(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle check suite event"""
        action = payload.get("action")
        check_suite = payload.get("check_suite", {})
        
        return {
            "action": action,
            "status": check_suite.get("status"),
            "conclusion": check_suite.get("conclusion"),
        }
    
    async def _handle_check_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle check run event"""
        action = payload.get("action")
        check_run = payload.get("check_run", {})
        
        return {
            "action": action,
            "name": check_run.get("name"),
            "status": check_run.get("status"),
            "conclusion": check_run.get("conclusion"),
        }
    
    async def _create_notification(
        self,
        title: str,
        message: str,
        notification_type: NotificationType,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Create a notification in the database"""
        try:
            async with AsyncSessionLocal() as session:
                notification = Notification(
                    title=title,
                    message=message,
                    type=notification_type,
                    source="github",
                    metadata=metadata or {},
                    created_at=datetime.utcnow(),
                    read=False
                )
                session.add(notification)
                await session.commit()
                
                logger.info(f"Created notification: {title}")
                
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
    
    async def _broadcast_update(self, event_type: str, payload: Dict[str, Any]):
        """Broadcast update via WebSocket"""
        try:
            # Extract key information for broadcast
            update_data = {
                "type": "github_event",
                "event": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "repository": payload.get("repository", {}).get("full_name"),
            }
            
            # Add event-specific data
            if event_type == "push":
                update_data["branch"] = payload.get("ref", "").replace("refs/heads/", "")
                update_data["commits"] = len(payload.get("commits", []))
            elif event_type == "pull_request":
                update_data["action"] = payload.get("action")
                update_data["pr_number"] = payload.get("pull_request", {}).get("number")
            elif event_type == "workflow_run":
                update_data["workflow"] = payload.get("workflow_run", {}).get("name")
                update_data["conclusion"] = payload.get("workflow_run", {}).get("conclusion")
            
            # Broadcast to all connected clients
            await websocket_manager.broadcast(json.dumps(update_data))
            
        except Exception as e:
            logger.error(f"Error broadcasting GitHub update: {e}")


# Singleton instance
github_webhook_handler = GitHubWebhookHandler()