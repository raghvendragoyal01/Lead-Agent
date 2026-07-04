# Lead Outbound Engine - Backend

## Project Overview

Lead Outbound Engine is a FastAPI backend that manages leads, campaigns, users, scraping, semantic search and vector database integration using PostgreSQL and Qdrant.

---

# Tech Stack

- FastAPI
- PostgreSQL
- SQLAlchemy
- Qdrant Vector Database
- Sentence Transformers (all-MiniLM-L6-v2)
- Playwright
- DuckDuckGo Search
- Google Search
- Python

---

# Project Structure

backend/
│
├── app/
│
├── ai_agents/
│   AI agent related modules.
│
├── core/
│   Core project utilities.
│
├── crud/
│   Database CRUD operations.
│   - campaign.py
│   - lead.py
│   - user.py
│
├── integrations/
│   Third party integrations.
│
├── models/
│   SQLAlchemy database models.
│   - campaign.py
│   - lead.py
│   - user.py
│
├── routes/
│   FastAPI API endpoints.
│   - campaign.py
│   - lead.py
│   - scraper.py
│   - search.py
│   - user.py
│
├── schemas/
│   Pydantic request/response schemas.
│   - campaign.py
│   - lead.py
│   - search.py
│   - user.py
│
├── scrapers/
│   Web scraping implementation.
│   - parser.py
│   - playwright_scraper.py
│   - search.py
│
├── search/
│   Search engine modules.
│   - ddg_client.py
│   - google_search.py
│   - search_service.py
│   - url_extractor.py
│
├── services/
│   Business logic layer.
│   - campaign_service.py
│   - lead_service.py
│   - scraper_service.py
│   - user_service.py
│
├── vector_db/
│   Qdrant Vector Database implementation.
│
│   ├── qdrant_client.py
│   │      Qdrant connection.
│   │
│   ├── embeddings.py
│   │      Generates sentence embeddings.
│   │
│   ├── store_vectors.py
│   │      Stores vectors into Qdrant.
│   │
│   ├── search_vectors.py
│   │      Semantic similarity search.
│   │
│   ├── sync_vectors.py
│   │      PostgreSQL → Qdrant synchronization.
│   │
│   ├── delete_vector.py
│   │      Deletes vectors.
│   │
│   ├── check_duplicate.py
│   │      Duplicate detection.
│   │
│   └── vector_service.py
│          Vector related helper functions.
│
├── tests/
│   Testing scripts.
│
│   ├── check_qdrant.py
│   │      Test Qdrant connection.
│   │
│   ├── test_embedding.py
│   │      Test embedding generation.
│   │
│   ├── test_store.py
│   │      Test vector storage.
│   │
│   ├── test_search.py
│   │      Test semantic search.
│   │
│   └── test_sync.py
│          Test PostgreSQL sync.
│
├── workers/
│   Background workers.
│
├── config.py
│   Application configuration.
│
├── database.py
│   PostgreSQL connection.
│
└── main.py
    FastAPI application entry point.

---

# Completed Features

## PostgreSQL

- Database connection
- SQLAlchemy models
- CRUD APIs
- Services
- Routes

---

## Qdrant

✔ Qdrant setup

✔ Collection creation

✔ Embedding generation

✔ Store vectors

✔ Semantic Search

✔ PostgreSQL → Qdrant Synchronization

✔ Create / Update Auto Sync

✔ Delete Sync

✔ Duplicate Detection

✔ Vector Testing

---

## Search

- Google Search
- DuckDuckGo Search
- URL Extraction
- Playwright Scraper

---

## API Modules

- User
- Lead
- Campaign
- Search
- Scraper

---

## Pending

- Google OAuth Authentication

---

# Notes

Current backend follows layered architecture.

Routes
↓

Services

↓

CRUD

↓

Database

↓

Vector Database (Qdrant)

This separation makes the project scalable and easy to maintain.
