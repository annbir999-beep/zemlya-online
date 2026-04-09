-- Enable PostGIS extension for geospatial queries
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- для full-text поиска

-- Индекс для поиска по cadastral_number
-- Создаётся после Alembic миграций
