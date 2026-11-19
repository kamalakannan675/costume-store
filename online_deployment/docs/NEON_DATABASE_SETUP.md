# Costume Store — Neon PostgreSQL Setup Guide

How to provision and integrate Neon Serverless PostgreSQL with the Costume Store application.

---

## 1. Why Neon PostgreSQL?

[Neon](https://neon.tech/) is a fully managed serverless PostgreSQL platform built for cloud applications:
- **Serverless Autoscaling**: Scales automatically and scales to zero when idle.
- **Built-in Connection Pooling**: Integrated PgBouncer pooler (`-pooler` endpoint) designed for serverless architectures like Vercel.
- **Generous Free Tier**: Includes 0.5 GB storage and 100 compute hours/month, suitable for college evaluations and production proofs.

---

## 2. Creating Your Neon Database

1. Sign up or log in to the [Neon Console](https://console.neon.tech/).
2. Click **Create Project**.
3. Name your project: `costume-store-db`.
4. Choose a region closest to your target audience (e.g. `ap-southeast-1` Singapore for India / Asia).
5. Click **Create Project**.

---

## 3. Obtaining the Connection String

On your Neon Project Dashboard:
1. Under **Connection Details**, ensure **Connection pooling** is checked.
2. Select **SQLAlchemy** or **psycopg2** from the format dropdown.
3. Your connection string will look like:
   ```text
   postgresql://neondb_owner:npg_SecretPass@ep-shiny-pond-a1b2c3d4-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Copy this string. It will be assigned to `DATABASE_URL` in Vercel.

---

## 4. Connection Pooling in Serverless Execution

Because Vercel serverless functions spin up ephemeral containers, direct PostgreSQL connections can accumulate quickly.

- **Always use the Pooled Connection String (`-pooler`)** provided by Neon.
- The application's `config.py` is configured with:
  ```python
  SQLALCHEMY_ENGINE_OPTIONS = {
      'pool_pre_ping': True,
      'pool_recycle': 300,
      'pool_size': 2,
      'max_overflow': 3,
      'pool_timeout': 30,
  }
  ```
- This configuration ensures that closed connections are discarded and recycled safely without overwhelming Neon.
