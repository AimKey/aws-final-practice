# AWS Final Practice - FastAPI Backend

## Project Overview

A small FastAPI backend that connects to AWS services and is deployed to an EC2 instance through a GitHub Actions CI/CD pipeline.

It provides:

- A health endpoint that reports service status, the deployed commit, and PostgreSQL (RDS) connectivity.
- An S3 connectivity check.
- A file upload endpoint that stores files in S3 and returns a presigned download URL.

**Tech stack:** Python 3.12, FastAPI, Uvicorn, psycopg2, boto3, Docker, GitHub Actions.

## Architecture Diagram

```mermaid
flowchart LR
    Client([Client])

    subgraph GitHub
        Repo[Repository<br/>main branch]
        Actions[GitHub Actions<br/>test + deploy]
    end

    subgraph AWS
        subgraph EC2[EC2 instance]
            Docker[Docker container<br/>FastAPI :8000]
        end
        RDS[(RDS PostgreSQL)]
        S3[(S3 bucket)]
    end

    Client -->|HTTP :8000| Docker
    Docker -->|psycopg2| RDS
    Docker -->|boto3| S3

    Repo -->|push to main| Actions
    Actions -->|SSH: git pull, docker build, compose up| EC2
```

Deployment flow: a push to `main` runs the tests, then the pipeline connects to the EC2 instance over SSH, pulls the latest code, rebuilds the Docker image, and restarts the container.

## Prerequisites

For local development:

- Python 3.12
- Docker and Docker Compose (optional, to run the container locally)
- A PostgreSQL database reachable from your machine (optional, only needed for a healthy `db` status)
- An S3 bucket and AWS credentials with access to it (optional, only needed for the S3 endpoints)

For deployment:

- An EC2 instance with Docker, the Docker Compose plugin, and Git installed
- The repository cloned on the instance
- A GitHub repository with the Actions secrets listed below

## Local Development Setup

### Run with Python

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env             # then fill in real values
uvicorn main:app --reload
```

The API is available at http://localhost:8000 and the interactive docs at http://localhost:8000/docs.

On your local machine there is no IAM role, so also add AWS credentials to `.env` (or export them in your shell):

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

### Run with Docker Compose

```bash
cp .env.example .env             # then fill in real values
docker compose up -d --build
```

### Run the tests

```bash
pytest -q
```

The tests mock the database and S3, so no credentials or network access are needed.

## AWS Resources

| Resource | Purpose |
|---|---|
| EC2 instance | Runs the Docker container and exposes port 8000. The security group must allow inbound TCP 22 (SSH, for deployment) and 8000 (API). |
| RDS PostgreSQL | Database the health endpoint connects to. Its security group must allow inbound 5432 from the EC2 instance. |
| S3 bucket | Stores uploaded files under the `uploads/` prefix. |
| IAM | The application needs `s3:ListBucket` (for the connectivity check) and `s3:PutObject` / `s3:GetObject` on the bucket. Attach an IAM role to the EC2 instance, or provide an access key pair. |

The default region is `ap-southeast-1`.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql://user:pass@localhost:5432/appdb` | PostgreSQL connection string. |
| `S3_BUCKET_NAME` | Yes | none | Name of the S3 bucket used for uploads. |
| `AWS_REGION` | No | `ap-southeast-1` | AWS region of the S3 bucket. |
| `AWS_ACCESS_KEY_ID` | No | none | Access key. Not needed when an IAM role is attached. |
| `AWS_SECRET_ACCESS_KEY` | No | none | Secret key. Not needed when an IAM role is attached. |
| `GIT_SHA` | No | `dev` | Commit hash shown by `/api/health`. Set as a Docker build argument by the pipeline. |

Variables are read from the environment, or from a `.env` file. The `.env` file is git-ignored; use `.env.example` as a template.

## Deployment Instructions

### Automatic deployment (GitHub Actions)

The workflow is defined in `.github/workflows/ci-cd.yml`.

- **Pull request to `main`:** runs the tests only.
- **Push to `main`:** runs the tests, and if they pass, deploys to EC2.

The deploy job connects to the instance over SSH and runs these steps:

1. `git pull --ff-only origin main`
2. Write `.env` from the GitHub secrets
3. `docker build --build-arg GIT_SHA=<commit> -t fastapi-app:local .`
4. `docker compose up -d --remove-orphans`
5. `docker image prune -f`

### Required GitHub Actions secrets

Add these under Settings > Secrets and variables > Actions:

| Secret | Description |
|---|---|
| `EC2_HOST` | Public IP or DNS name of the EC2 instance. |
| `EC2_USER` | SSH user, for example `ec2-user`. |
| `EC2_SSH_KEY` | Full contents of the private key (`.pem`) used to SSH into the instance. |
| `DATABASE_URL` | PostgreSQL connection string. |
| `S3_BUCKET_NAME` | S3 bucket name. |
| `AWS_ACCESS_KEY_ID` | AWS access key. |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key. |

### One-time EC2 setup

```bash
git clone https://github.com/AimKey/aws-final-practice.git /home/ec2-user/aws-final-practice
```

The deploy script expects the repository at `/home/ec2-user/aws-final-practice`. The SSH user must be able to run `docker` without `sudo` and to run `git pull` in that directory.

### Manual deployment

```bash
cd /home/ec2-user/aws-final-practice
git pull --ff-only origin main
docker build --build-arg GIT_SHA="$(git rev-parse HEAD)" -t fastapi-app:local .
docker compose up -d --remove-orphans
```

### Verify

```bash
curl http://<EC2_HOST>:8000/api/health
```

The `commit` field in the response should match the commit you deployed.

## API Documentation

Interactive documentation is generated by FastAPI at `/docs` (Swagger UI) and `/redoc`.

### `GET /api/health`

Reports service status and database connectivity. It always returns HTTP 200; check the `db` field for the database state.

Response:

```json
{
  "status": "ok",
  "service": "backend",
  "commit": "a9a8fa4",
  "db": "connected",
  "db_version": "PostgreSQL 16.1"
}
```

If the database cannot be reached, `db` is `"error: <message>"` and `db_version` is `null`.

### `GET /api/s3/test`

Checks that the configured S3 bucket is reachable.

Success:

```json
{
  "status": "ok",
  "bucket": "your-bucket-name",
  "message": "Connected to S3 successfully"
}
```

Failure (HTTP 200 with an error body):

```json
{
  "status": "error",
  "error_code": "403",
  "detail": "..."
}
```

### `POST /api/s3/upload`

Uploads a file to S3 under `uploads/<random-id><extension>` and returns a presigned download URL valid for 1 hour.

Request: `multipart/form-data` with a `file` field. Maximum size is 10 MB.

```bash
curl -F "file=@photo.png" http://localhost:8000/api/s3/upload
```

Response (200):

```json
{
  "key": "uploads/3f2a9c0d1e4b4c7f8a6b5d4e3c2b1a09.png",
  "filename": "photo.png",
  "content_type": "image/png",
  "size": 48213,
  "url": "https://your-bucket-name.s3.amazonaws.com/uploads/...?X-Amz-Signature=..."
}
```

Errors:

| Status | Reason |
|---|---|
| 400 | The file is empty. |
| 413 | The file is larger than 10 MB. |
| 502 | S3 returned an error. The error code is included in the message. |
