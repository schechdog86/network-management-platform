# GitHub GraphQL API Examples for Network Management Platform

This document contains useful GraphQL queries and mutations for interacting with the Network Management Platform repository.

## Authentication

First, you'll need a GitHub personal access token with appropriate permissions:
- `repo` scope for private repositories
- `public_repo` scope for public repositories

## Basic Repository Query

Query to get basic information about the repository:

```graphql
query GetRepositoryInfo {
  repository(owner: "schechdog86", name: "network-management-platform") {
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
          color
        }
        size
      }
    }
    diskUsage
    forkCount
    stargazerCount
  }
}
```

## Query Branches

Get information about all branches:

```graphql
query GetBranches {
  repository(owner: "schechdog86", name: "network-management-platform") {
    refs(refPrefix: "refs/heads/", first: 10) {
      nodes {
        name
        target {
          ... on Commit {
            committedDate
            message
            author {
              name
              email
            }
          }
        }
      }
    }
  }
}
```

## Query Recent Commits

Get the last 10 commits from the v2 branch:

```graphql
query GetRecentCommits {
  repository(owner: "schechdog86", name: "network-management-platform") {
    ref(qualifiedName: "refs/heads/v2") {
      target {
        ... on Commit {
          history(first: 10) {
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
```

## Query File Contents

Get the contents of a specific file:

```graphql
query GetFileContent {
  repository(owner: "schechdog86", name: "network-management-platform") {
    object(expression: "v2:README.md") {
      ... on Blob {
        text
        byteSize
      }
    }
  }
}
```

## Query Directory Structure

Get the directory structure of the ubuntu-core folder:

```graphql
query GetDirectoryStructure {
  repository(owner: "schechdog86", name: "network-management-platform") {
    object(expression: "v2:ubuntu-core") {
      ... on Tree {
        entries {
          name
          type
          object {
            ... on Blob {
              byteSize
            }
            ... on Tree {
              entries {
                name
                type
              }
            }
          }
        }
      }
    }
  }
}
```

## Create an Issue

Mutation to create a new issue:

```graphql
mutation CreateIssue {
  createIssue(input: {
    repositoryId: "REPOSITORY_ID_HERE",
    title: "Enhancement: Add Kubernetes support",
    body: "We should add support for deploying the snaps on Kubernetes clusters.",
    labelIds: ["LABEL_ID_HERE"]
  }) {
    issue {
      id
      number
      title
      url
    }
  }
}
```

## Add a Star

Mutation to star the repository:

```graphql
mutation AddStar {
  addStar(input: {
    starrableId: "REPOSITORY_ID_HERE"
  }) {
    starrable {
      ... on Repository {
        stargazerCount
        viewerHasStarred
      }
    }
  }
}
```

## Query Pull Requests

Get open pull requests:

```graphql
query GetPullRequests {
  repository(owner: "schechdog86", name: "network-management-platform") {
    pullRequests(first: 10, states: OPEN) {
      edges {
        node {
          number
          title
          author {
            login
          }
          createdAt
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
```

## Query Issues with Labels

Get issues with specific labels:

```graphql
query GetIssuesWithLabels {
  repository(owner: "schechdog86", name: "network-management-platform") {
    issues(first: 20, labels: ["enhancement", "help wanted"], states: OPEN) {
      edges {
        node {
          number
          title
          author {
            login
          }
          createdAt
          labels(first: 5) {
            edges {
              node {
                name
                color
              }
            }
          }
        }
      }
    }
  }
}
```

## Get Repository ID

To get the repository ID for mutations:

```graphql
query GetRepositoryId {
  repository(owner: "schechdog86", name: "network-management-platform") {
    id
  }
}
```

## Using Variables

Example using variables for better reusability:

```graphql
query GetRepositoryDetails($owner: String!, $name: String!, $numIssues: Int = 5) {
  repository(owner: $owner, name: $name) {
    name
    description
    issues(first: $numIssues, states: OPEN) {
      totalCount
      edges {
        node {
          title
          number
        }
      }
    }
  }
}
```

Variables:
```json
{
  "owner": "schechdog86",
  "name": "network-management-platform",
  "numIssues": 10
}
```

## cURL Examples

### Basic Query with cURL

```bash
curl -H "Authorization: bearer YOUR_TOKEN" -X POST -d '
{
  "query": "query { repository(owner:\"schechdog86\", name:\"network-management-platform\") { name description stargazerCount } }"
}
' https://api.github.com/graphql
```

### Query with Variables

```bash
curl -H "Authorization: bearer YOUR_TOKEN" -X POST -d '
{
  "query": "query($owner:String!, $name:String!) { repository(owner:$owner, name:$name) { name description } }",
  "variables": {
    "owner": "schechdog86",
    "name": "network-management-platform"
  }
}
' https://api.github.com/graphql
```

## Python Example

```python
import requests
import json

# Your GitHub token
token = "YOUR_GITHUB_TOKEN"

# GraphQL endpoint
url = "https://api.github.com/graphql"

# Headers
headers = {
    "Authorization": f"bearer {token}",
    "Content-Type": "application/json"
}

# Query
query = """
query {
  repository(owner: "schechdog86", name: "network-management-platform") {
    name
    description
    stargazerCount
    forkCount
    issues(states: OPEN) {
      totalCount
    }
    pullRequests(states: OPEN) {
      totalCount
    }
  }
}
"""

# Make request
response = requests.post(url, headers=headers, json={"query": query})

# Print result
print(json.dumps(response.json(), indent=2))
```

## JavaScript Example

```javascript
const fetch = require('node-fetch');

const token = 'YOUR_GITHUB_TOKEN';

const query = `
  query {
    repository(owner: "schechdog86", name: "network-management-platform") {
      name
      description
      stargazerCount
      defaultBranchRef {
        name
        target {
          ... on Commit {
            history(first: 5) {
              edges {
                node {
                  message
                  committedDate
                }
              }
            }
          }
        }
      }
    }
  }
`;

fetch('https://api.github.com/graphql', {
  method: 'POST',
  headers: {
    'Authorization': `bearer ${token}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ query }),
})
  .then(res => res.json())
  .then(data => console.log(JSON.stringify(data, null, 2)));
```

## Useful Fragments

Define reusable fragments for common queries:

```graphql
fragment RepoInfo on Repository {
  name
  description
  url
  stargazerCount
  forkCount
}

fragment CommitInfo on Commit {
  oid
  message
  committedDate
  author {
    name
    email
  }
}

query GetRepoWithFragments {
  repository(owner: "schechdog86", name: "network-management-platform") {
    ...RepoInfo
    defaultBranchRef {
      target {
        ... on Commit {
          ...CommitInfo
        }
      }
    }
  }
}
```

## Rate Limiting

Check your rate limit status:

```graphql
query {
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
```

## Schema Introspection

Get information about the GraphQL schema:

```graphql
query {
  __type(name: "Repository") {
    name
    kind
    description
    fields {
      name
      description
      type {
        name
        kind
      }
    }
  }
}
```

---

Remember to replace `YOUR_TOKEN` with your actual GitHub personal access token and `REPOSITORY_ID_HERE` with the actual repository ID when needed.