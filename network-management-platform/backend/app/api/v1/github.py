"""
GitHub integration API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.services.github_integration import (
    github_service,
    GitHubRepository,
    GitHubCommit,
    GitHubIssue,
    GitHubPullRequest,
    GitHubWorkflowRun
)
from app.api.deps import get_current_user
from app.models.user import User
from app.core.logging_config import logger

router = APIRouter(prefix="/github", tags=["github"])


@router.get("/repository", response_model=GitHubRepository)
async def get_repository_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get repository information including stats, languages, and counts.
    """
    try:
        async with github_service as service:
            return await service.get_repository_info()
    except Exception as e:
        logger.error(f"Error fetching repository info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commits", response_model=List[GitHubCommit])
async def get_recent_commits(
    branch: str = Query("v2", description="Branch name"),
    limit: int = Query(10, ge=1, le=100, description="Number of commits to fetch"),
    current_user: User = Depends(get_current_user)
):
    """
    Get recent commits from specified branch.
    """
    try:
        async with github_service as service:
            return await service.get_recent_commits(branch=branch, limit=limit)
    except Exception as e:
        logger.error(f"Error fetching commits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issues", response_model=List[GitHubIssue])
async def get_open_issues(
    labels: Optional[List[str]] = Query(None, description="Filter by labels"),
    limit: int = Query(20, ge=1, le=100, description="Number of issues to fetch"),
    current_user: User = Depends(get_current_user)
):
    """
    Get open issues, optionally filtered by labels.
    """
    try:
        async with github_service as service:
            return await service.get_open_issues(labels=labels, limit=limit)
    except Exception as e:
        logger.error(f"Error fetching issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pull-requests", response_model=List[GitHubPullRequest])
async def get_open_pull_requests(
    limit: int = Query(20, ge=1, le=100, description="Number of PRs to fetch"),
    current_user: User = Depends(get_current_user)
):
    """
    Get open pull requests.
    """
    try:
        async with github_service as service:
            return await service.get_open_pull_requests(limit=limit)
    except Exception as e:
        logger.error(f"Error fetching pull requests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow-runs", response_model=List[GitHubWorkflowRun])
async def get_workflow_runs(
    limit: int = Query(10, ge=1, le=50, description="Number of workflow runs to fetch"),
    current_user: User = Depends(get_current_user)
):
    """
    Get recent workflow runs (CI/CD status).
    """
    try:
        async with github_service as service:
            return await service.get_workflow_runs(limit=limit)
    except Exception as e:
        logger.error(f"Error fetching workflow runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rate-limit")
async def get_rate_limit_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get current GitHub API rate limit status.
    """
    try:
        async with github_service as service:
            return await service.get_rate_limit_status()
    except Exception as e:
        logger.error(f"Error fetching rate limit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/issues")
async def create_issue(
    title: str,
    body: str,
    labels: Optional[List[str]] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new issue in the repository.
    Requires admin privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    try:
        async with github_service as service:
            return await service.create_issue(title=title, body=body, labels=labels)
    except Exception as e:
        logger.error(f"Error creating issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_repository_stats_summary(
    current_user: User = Depends(get_current_user)
):
    """
    Get a comprehensive summary of repository statistics.
    """
    try:
        async with github_service as service:
            # Fetch multiple data points concurrently
            repo_info = await service.get_repository_info()
            recent_commits = await service.get_recent_commits(limit=30)
            open_issues = await service.get_open_issues(limit=100)
            open_prs = await service.get_open_pull_requests(limit=100)
            
            # Calculate commit stats
            commits_last_7_days = 0
            commits_last_30_days = 0
            now = datetime.now(timezone.utc)
            
            for commit in recent_commits:
                days_ago = (now - commit.committed_date).days
                if days_ago <= 7:
                    commits_last_7_days += 1
                if days_ago <= 30:
                    commits_last_30_days += 1
            
            # Calculate issue stats
            bug_issues = [i for i in open_issues if "bug" in i.labels]
            enhancement_issues = [i for i in open_issues if "enhancement" in i.labels]
            
            return {
                "repository": {
                    "name": repo_info.name,
                    "description": repo_info.description,
                    "url": repo_info.url,
                    "stars": repo_info.stargazer_count,
                    "forks": repo_info.fork_count,
                    "disk_usage_mb": repo_info.disk_usage / 1024,
                    "is_private": repo_info.is_private,
                    "default_branch": repo_info.default_branch,
                    "languages": repo_info.languages
                },
                "activity": {
                    "commits_last_7_days": commits_last_7_days,
                    "commits_last_30_days": commits_last_30_days,
                    "total_open_issues": len(open_issues),
                    "bug_issues": len(bug_issues),
                    "enhancement_issues": len(enhancement_issues),
                    "open_pull_requests": len(open_prs)
                },
                "recent_activity": {
                    "latest_commit": recent_commits[0].dict() if recent_commits else None,
                    "latest_issue": open_issues[0].dict() if open_issues else None,
                    "latest_pr": open_prs[0].dict() if open_prs else None
                }
            }
    except Exception as e:
        logger.error(f"Error fetching repository stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))