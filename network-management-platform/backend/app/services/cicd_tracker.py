"""
CI/CD tracking service for monitoring build status and deployment pipelines.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from app.services.github_integration import github_service, GitHubWorkflowRun
from app.core.logging_config import logger
from app.db.session import AsyncSessionLocal
from app.models.device import Device
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update


class DeploymentStatus(str, Enum):
    """Deployment status enum"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeploymentEnvironment(str, Enum):
    """Deployment environment enum"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class CICDTracker:
    """Service for tracking CI/CD pipelines and deployments"""
    
    def __init__(self):
        self.workflow_cache: Dict[str, GitHubWorkflowRun] = {}
        self.deployment_history: List[Dict[str, Any]] = []
        self.monitoring_interval = 60  # seconds
        self._monitoring_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self):
        """Start monitoring CI/CD pipelines"""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("CI/CD monitoring already running")
            return
        
        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("Started CI/CD monitoring")
    
    async def stop_monitoring(self):
        """Stop monitoring CI/CD pipelines"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped CI/CD monitoring")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await self._check_workflow_status()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in CI/CD monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _check_workflow_status(self):
        """Check GitHub Actions workflow status"""
        try:
            async with github_service as service:
                workflow_runs = await service.get_workflow_runs(limit=20)
                
                for run in workflow_runs:
                    # Check if this is a new or updated run
                    if run.id not in self.workflow_cache or \
                       self.workflow_cache[run.id].updated_at != run.updated_at:
                        
                        # Process workflow run
                        await self._process_workflow_run(run)
                        
                        # Update cache
                        self.workflow_cache[run.id] = run
                
        except Exception as e:
            logger.error(f"Error checking workflow status: {e}")
    
    async def _process_workflow_run(self, run: GitHubWorkflowRun):
        """Process a workflow run and trigger actions based on status"""
        logger.info(f"Processing workflow run: {run.name} (#{run.run_number}) - {run.status}")
        
        # Determine if this is a deployment workflow
        if self._is_deployment_workflow(run):
            await self._handle_deployment(run)
        
        # Check for failed builds
        if run.status == "COMPLETED" and run.conclusion == "FAILURE":
            await self._handle_build_failure(run)
        
        # Check for successful deployments
        if run.status == "COMPLETED" and run.conclusion == "SUCCESS":
            await self._handle_build_success(run)
    
    def _is_deployment_workflow(self, run: GitHubWorkflowRun) -> bool:
        """Check if workflow is a deployment workflow"""
        deployment_keywords = ["deploy", "release", "publish"]
        return any(keyword in run.name.lower() for keyword in deployment_keywords)
    
    async def _handle_deployment(self, run: GitHubWorkflowRun):
        """Handle deployment workflow"""
        environment = self._detect_environment(run)
        
        deployment_record = {
            "workflow_id": run.id,
            "workflow_name": run.name,
            "run_number": run.run_number,
            "environment": environment,
            "status": self._map_workflow_status_to_deployment(run),
            "started_at": run.created_at,
            "updated_at": run.updated_at,
            "commit_sha": run.head_sha,
            "branch": run.head_branch,
        }
        
        # Add to deployment history
        self.deployment_history.append(deployment_record)
        
        # Keep only last 100 deployments
        if len(self.deployment_history) > 100:
            self.deployment_history = self.deployment_history[-100:]
        
        # If deployment to production succeeded, update device statuses
        if environment == DeploymentEnvironment.PRODUCTION and \
           deployment_record["status"] == DeploymentStatus.SUCCESS:
            await self._update_device_deployment_status(run)
    
    def _detect_environment(self, run: GitHubWorkflowRun) -> DeploymentEnvironment:
        """Detect deployment environment from workflow name or branch"""
        name_lower = run.name.lower()
        branch_lower = run.head_branch.lower()
        
        if "prod" in name_lower or "production" in name_lower or branch_lower == "main":
            return DeploymentEnvironment.PRODUCTION
        elif "staging" in name_lower or branch_lower == "staging":
            return DeploymentEnvironment.STAGING
        else:
            return DeploymentEnvironment.DEVELOPMENT
    
    def _map_workflow_status_to_deployment(self, run: GitHubWorkflowRun) -> DeploymentStatus:
        """Map GitHub workflow status to deployment status"""
        if run.status != "COMPLETED":
            return DeploymentStatus.IN_PROGRESS
        
        if run.conclusion == "SUCCESS":
            return DeploymentStatus.SUCCESS
        elif run.conclusion == "FAILURE":
            return DeploymentStatus.FAILED
        elif run.conclusion == "CANCELLED":
            return DeploymentStatus.CANCELLED
        else:
            return DeploymentStatus.PENDING
    
    async def _handle_build_failure(self, run: GitHubWorkflowRun):
        """Handle build failure"""
        logger.error(f"Build failed: {run.name} (#{run.run_number})")
        
        # Could send notifications, create issues, etc.
        # For now, just log the failure
    
    async def _handle_build_success(self, run: GitHubWorkflowRun):
        """Handle build success"""
        logger.info(f"Build succeeded: {run.name} (#{run.run_number})")
        
        # Could trigger subsequent actions
    
    async def _update_device_deployment_status(self, run: GitHubWorkflowRun):
        """Update device deployment status after successful production deployment"""
        try:
            async with AsyncSessionLocal() as session:
                # Update all devices to mark them as having the latest deployment
                await session.execute(
                    update(Device).values(
                        last_deployment_at=datetime.utcnow(),
                        deployment_version=run.head_sha[:7],  # Short commit SHA
                        deployment_status="up-to-date"
                    )
                )
                await session.commit()
                logger.info(f"Updated device deployment status for commit {run.head_sha[:7]}")
        except Exception as e:
            logger.error(f"Error updating device deployment status: {e}")
    
    async def get_deployment_status(self, environment: Optional[DeploymentEnvironment] = None) -> Dict[str, Any]:
        """Get current deployment status"""
        deployments = self.deployment_history
        
        if environment:
            deployments = [d for d in deployments if d["environment"] == environment]
        
        # Get latest deployment per environment
        latest_by_env = {}
        for deployment in deployments:
            env = deployment["environment"]
            if env not in latest_by_env or deployment["updated_at"] > latest_by_env[env]["updated_at"]:
                latest_by_env[env] = deployment
        
        # Calculate statistics
        total_deployments = len(self.deployment_history)
        successful_deployments = len([d for d in self.deployment_history if d["status"] == DeploymentStatus.SUCCESS])
        failed_deployments = len([d for d in self.deployment_history if d["status"] == DeploymentStatus.FAILED])
        
        success_rate = (successful_deployments / total_deployments * 100) if total_deployments > 0 else 0
        
        return {
            "latest_deployments": latest_by_env,
            "statistics": {
                "total_deployments": total_deployments,
                "successful_deployments": successful_deployments,
                "failed_deployments": failed_deployments,
                "success_rate": round(success_rate, 2),
            },
            "recent_deployments": deployments[:10],  # Last 10 deployments
        }
    
    async def get_workflow_metrics(self) -> Dict[str, Any]:
        """Get workflow execution metrics"""
        if not self.workflow_cache:
            return {
                "total_runs": 0,
                "average_duration": 0,
                "success_rate": 0,
                "workflows_by_status": {},
            }
        
        workflows = list(self.workflow_cache.values())
        completed_workflows = [w for w in workflows if w.status == "COMPLETED"]
        
        # Calculate metrics
        total_runs = len(workflows)
        successful_runs = len([w for w in completed_workflows if w.conclusion == "SUCCESS"])
        failed_runs = len([w for w in completed_workflows if w.conclusion == "FAILURE"])
        
        # Calculate average duration for completed workflows
        durations = []
        for workflow in completed_workflows:
            duration = (workflow.updated_at - workflow.created_at).total_seconds()
            durations.append(duration)
        
        average_duration = sum(durations) / len(durations) if durations else 0
        
        # Success rate
        success_rate = (successful_runs / len(completed_workflows) * 100) if completed_workflows else 0
        
        # Group by status
        workflows_by_status = {
            "in_progress": len([w for w in workflows if w.status != "COMPLETED"]),
            "successful": successful_runs,
            "failed": failed_runs,
            "cancelled": len([w for w in completed_workflows if w.conclusion == "CANCELLED"]),
        }
        
        return {
            "total_runs": total_runs,
            "average_duration_seconds": round(average_duration, 2),
            "success_rate": round(success_rate, 2),
            "workflows_by_status": workflows_by_status,
        }
    
    async def trigger_deployment(self, environment: DeploymentEnvironment, branch: str = "main") -> Dict[str, Any]:
        """Trigger a deployment (placeholder for actual implementation)"""
        # This would integrate with GitHub Actions API to trigger a workflow
        # For now, return a mock response
        return {
            "status": "triggered",
            "environment": environment,
            "branch": branch,
            "message": "Deployment workflow triggered successfully",
            "workflow_id": f"mock-{datetime.utcnow().isoformat()}",
        }


# Singleton instance
cicd_tracker = CICDTracker()