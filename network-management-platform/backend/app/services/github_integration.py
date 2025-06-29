"""
GitHub GraphQL API integration service for repository monitoring and CI/CD tracking.
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import httpx
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.logging_config import logger


class GitHubCommit(BaseModel):
    """GitHub commit model"""
    oid: str
    message: str
    committed_date: datetime
    author_name: str
    author_email: str
    additions: int = 0
    deletions: int = 0


class GitHubIssue(BaseModel):
    """GitHub issue model"""
    number: int
    title: str
    state: str
    created_at: datetime
    author: str
    labels: List[str] = []


class GitHubPullRequest(BaseModel):
    """GitHub pull request model"""
    number: int
    title: str
    state: str
    created_at: datetime
    author: str
    head_ref: str
    base_ref: str
    mergeable: Optional[bool] = None
    additions: int = 0
    deletions: int = 0


class GitHubRepository(BaseModel):
    """GitHub repository model"""
    name: str
    description: Optional[str] = None
    url: str
    created_at: datetime
    updated_at: datetime
    is_private: bool
    default_branch: str
    disk_usage: int
    fork_count: int
    stargazer_count: int
    open_issues_count: int = 0
    open_prs_count: int = 0
    languages: Dict[str, int] = {}


class GitHubWorkflowRun(BaseModel):
    """GitHub workflow run model"""
    id: str
    name: str
    status: str
    conclusion: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    head_sha: str
    head_branch: str
    run_number: int
    event: str


class GitHubIntegrationService:
    """Service for GitHub GraphQL API integration"""
    
    def __init__(self):
        self.api_url = "https://api.github.com/graphql"
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.owner = "schechdog86"
        self.repo = "network-management-platform"
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"bearer {self.token}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query"""
        try:
            response = await self.client.post(
                self.api_url,
                json={"query": query, "variables": variables or {}}
            )
            response.raise_for_status()
            
            data = response.json()
            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                raise Exception(f"GraphQL query failed: {data['errors']}")
            
            return data.get("data", {})
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error executing GraphQL query: {e}")
            raise
        except Exception as e:
            logger.error(f"Error executing GraphQL query: {e}")
            raise
    
    async def get_repository_info(self) -> GitHubRepository:
        """Get repository information"""
        query = """
        query GetRepositoryInfo($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            name
            description
            url
            createdAt
            updatedAt
            isPrivate
            defaultBranchRef {
              name
            }
            languages(first: 10) {
              edges {
                node {
                  name
                }
                size
              }
            }
            diskUsage
            forkCount
            stargazerCount
            issues(states: OPEN) {
              totalCount
            }
            pullRequests(states: OPEN) {
              totalCount
            }
          }
        }
        """
        
        variables = {"owner": self.owner, "name": self.repo}
        data = await self.execute_query(query, variables)
        
        repo_data = data.get("repository", {})
        
        # Process languages
        languages = {}
        for edge in repo_data.get("languages", {}).get("edges", []):
            languages[edge["node"]["name"]] = edge["size"]
        
        return GitHubRepository(
            name=repo_data["name"],
            description=repo_data.get("description"),
            url=repo_data["url"],
            created_at=datetime.fromisoformat(repo_data["createdAt"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(repo_data["updatedAt"].replace("Z", "+00:00")),
            is_private=repo_data["isPrivate"],
            default_branch=repo_data["defaultBranchRef"]["name"],
            disk_usage=repo_data["diskUsage"],
            fork_count=repo_data["forkCount"],
            stargazer_count=repo_data["stargazerCount"],
            open_issues_count=repo_data.get("issues", {}).get("totalCount", 0),
            open_prs_count=repo_data.get("pullRequests", {}).get("totalCount", 0),
            languages=languages
        )
    
    async def get_recent_commits(self, branch: str = "v2", limit: int = 10) -> List[GitHubCommit]:
        """Get recent commits from a branch"""
        query = """
        query GetRecentCommits($owner: String!, $name: String!, $branch: String!, $limit: Int!) {
          repository(owner: $owner, name: $name) {
            ref(qualifiedName: $branch) {
              target {
                ... on Commit {
                  history(first: $limit) {
                    edges {
                      node {
                        oid
                        message
                        committedDate
                        author {
                          name
                          email
                        }
                        additions
                        deletions
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "owner": self.owner,
            "name": self.repo,
            "branch": f"refs/heads/{branch}",
            "limit": limit
        }
        
        data = await self.execute_query(query, variables)
        
        commits = []
        edges = data.get("repository", {}).get("ref", {}).get("target", {}).get("history", {}).get("edges", [])
        
        for edge in edges:
            node = edge["node"]
            commits.append(GitHubCommit(
                oid=node["oid"],
                message=node["message"],
                committed_date=datetime.fromisoformat(node["committedDate"].replace("Z", "+00:00")),
                author_name=node["author"]["name"],
                author_email=node["author"]["email"],
                additions=node.get("additions", 0),
                deletions=node.get("deletions", 0)
            ))
        
        return commits
    
    async def get_open_issues(self, labels: Optional[List[str]] = None, limit: int = 20) -> List[GitHubIssue]:
        """Get open issues, optionally filtered by labels"""
        query = """
        query GetOpenIssues($owner: String!, $name: String!, $labels: [String!], $limit: Int!) {
          repository(owner: $owner, name: $name) {
            issues(first: $limit, labels: $labels, states: OPEN, orderBy: {field: CREATED_AT, direction: DESC}) {
              edges {
                node {
                  number
                  title
                  state
                  createdAt
                  author {
                    login
                  }
                  labels(first: 10) {
                    edges {
                      node {
                        name
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "owner": self.owner,
            "name": self.repo,
            "labels": labels,
            "limit": limit
        }
        
        data = await self.execute_query(query, variables)
        
        issues = []
        edges = data.get("repository", {}).get("issues", {}).get("edges", [])
        
        for edge in edges:
            node = edge["node"]
            issue_labels = [label_edge["node"]["name"] 
                          for label_edge in node.get("labels", {}).get("edges", [])]
            
            issues.append(GitHubIssue(
                number=node["number"],
                title=node["title"],
                state=node["state"],
                created_at=datetime.fromisoformat(node["createdAt"].replace("Z", "+00:00")),
                author=node["author"]["login"] if node.get("author") else "unknown",
                labels=issue_labels
            ))
        
        return issues
    
    async def get_open_pull_requests(self, limit: int = 20) -> List[GitHubPullRequest]:
        """Get open pull requests"""
        query = """
        query GetOpenPullRequests($owner: String!, $name: String!, $limit: Int!) {
          repository(owner: $owner, name: $name) {
            pullRequests(first: $limit, states: OPEN, orderBy: {field: CREATED_AT, direction: DESC}) {
              edges {
                node {
                  number
                  title
                  state
                  createdAt
                  author {
                    login
                  }
                  headRefName
                  baseRefName
                  mergeable
                  additions
                  deletions
                }
              }
            }
          }
        }
        """
        
        variables = {
            "owner": self.owner,
            "name": self.repo,
            "limit": limit
        }
        
        data = await self.execute_query(query, variables)
        
        prs = []
        edges = data.get("repository", {}).get("pullRequests", {}).get("edges", [])
        
        for edge in edges:
            node = edge["node"]
            prs.append(GitHubPullRequest(
                number=node["number"],
                title=node["title"],
                state=node["state"],
                created_at=datetime.fromisoformat(node["createdAt"].replace("Z", "+00:00")),
                author=node["author"]["login"] if node.get("author") else "unknown",
                head_ref=node["headRefName"],
                base_ref=node["baseRefName"],
                mergeable=node.get("mergeable"),
                additions=node.get("additions", 0),
                deletions=node.get("deletions", 0)
            ))
        
        return prs
    
    async def get_workflow_runs(self, limit: int = 10) -> List[GitHubWorkflowRun]:
        """Get recent workflow runs (GitHub Actions)"""
        query = """
        query GetWorkflowRuns($owner: String!, $name: String!, $limit: Int!) {
          repository(owner: $owner, name: $name) {
            defaultBranchRef {
              target {
                ... on Commit {
                  checkSuites(first: $limit) {
                    edges {
                      node {
                        id
                        status
                        conclusion
                        createdAt
                        updatedAt
                        commit {
                          oid
                        }
                        checkRuns(first: 1) {
                          nodes {
                            name
                          }
                        }
                        app {
                          name
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        # Note: GitHub Actions runs are exposed through check suites in GraphQL
        # For more detailed workflow information, REST API might be needed
        
        variables = {
            "owner": self.owner,
            "name": self.repo,
            "limit": limit
        }
        
        data = await self.execute_query(query, variables)
        
        runs = []
        target = data.get("repository", {}).get("defaultBranchRef", {}).get("target", {})
        edges = target.get("checkSuites", {}).get("edges", [])
        
        for i, edge in enumerate(edges):
            node = edge["node"]
            run_name = "GitHub Actions"
            if node.get("checkRuns", {}).get("nodes"):
                run_name = node["checkRuns"]["nodes"][0]["name"]
            
            runs.append(GitHubWorkflowRun(
                id=node["id"],
                name=run_name,
                status=node["status"],
                conclusion=node.get("conclusion"),
                created_at=datetime.fromisoformat(node["createdAt"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(node["updatedAt"].replace("Z", "+00:00")),
                head_sha=node["commit"]["oid"],
                head_branch=self.owner,  # Default branch
                run_number=i + 1,
                event="push"  # Default event type
            ))
        
        return runs
    
    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        query = """
        query GetRateLimit {
          rateLimit {
            limit
            cost
            remaining
            resetAt
          }
          viewer {
            login
          }
        }
        """
        
        data = await self.execute_query(query)
        
        rate_limit = data.get("rateLimit", {})
        viewer = data.get("viewer", {})
        
        return {
            "limit": rate_limit.get("limit"),
            "cost": rate_limit.get("cost"),
            "remaining": rate_limit.get("remaining"),
            "reset_at": rate_limit.get("resetAt"),
            "authenticated_user": viewer.get("login")
        }
    
    async def create_issue(self, title: str, body: str, labels: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a new issue"""
        # First, get repository ID
        repo_id_query = """
        query GetRepositoryId($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            id
          }
        }
        """
        
        variables = {"owner": self.owner, "name": self.repo}
        repo_data = await self.execute_query(repo_id_query, variables)
        repo_id = repo_data["repository"]["id"]
        
        # Create issue mutation
        mutation = """
        mutation CreateIssue($input: CreateIssueInput!) {
          createIssue(input: $input) {
            issue {
              id
              number
              title
              url
            }
          }
        }
        """
        
        variables = {
            "input": {
                "repositoryId": repo_id,
                "title": title,
                "body": body
            }
        }
        
        # TODO: Add label IDs if labels are provided
        
        data = await self.execute_query(mutation, variables)
        return data.get("createIssue", {}).get("issue", {})


# Singleton instance
github_service = GitHubIntegrationService()