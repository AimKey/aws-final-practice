from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import psycopg2
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/appdb")
COMMIT = os.getenv("GIT_SHA", "dev")[:7]


@app.get("/api/health")
def health():
    db_status = "unhealthy"
    db_version = None
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                db_version = cur.fetchone()[0].split(" on ")[0]
        finally:
            conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    return {
        "status": "ok",
        "service": "backend",
        "commit": COMMIT,
        "db": db_status,
        "db_version": db_version,
    }

# S3
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")

s3_client = boto3.client("s3", region_name=AWS_REGION)

@app.get("/api/s3/test")
def test_s3():
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
        return {"status": "ok", "bucket": S3_BUCKET_NAME, "message": "Connected to S3 successfully"}
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        return {"status": "error", "error_code": error_code, "detail": str(e)}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

@app.post("/api/s3/upload")
def upload_file(file: UploadFile = File(...)):
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size == 0:
        raise HTTPException(400, "File rỗng")
    if size > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"File vượt quá {MAX_UPLOAD_SIZE // 1024 // 1024}MB")

    ext = os.path.splitext(file.filename or "")[1].lower()
    key = f"uploads/{uuid.uuid4().hex}{ext}"
    content_type = file.content_type or "application/octet-stream"

    try:
        s3_client.upload_fileobj(file.file, S3_BUCKET_NAME, key, ExtraArgs={"ContentType": content_type})
        url = s3_client.generate_presigned_url(
            "get_object", Params={"Bucket": S3_BUCKET_NAME, "Key": key}, ExpiresIn=3600
        )
    except ClientError as e:
        raise HTTPException(502, f"S3 error: {e.response['Error']['Code']}")

    return {
        "key": key,
        "filename": file.filename,
        "content_type": content_type,
        "size": size,
        "url": url,
    }
