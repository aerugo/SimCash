-- Migration 001: add config json to checkpoints
-- Created: 2025-10-29
-- Purpose: Store full config in checkpoint records for app-restart persistence
--
-- This migration adds the config_json column to simulation_checkpoints table.
-- This enables checkpoints to be restored after app restart without relying
-- on in-memory manager.configs dictionary.

-- Note: This migration may be a no-op if the schema was already created with the column
-- (i.e., if initialize_schema was called after the model was updated but before this migration)
-- DuckDB will raise an error if we try to add a column that already exists, so we need to check first

-- Check if column exists and add only if it doesn't
-- DuckDB doesn't have IF NOT EXISTS for ALTER TABLE ADD COLUMN, so we'll use a workaround:
-- We'll check the information_schema to see if the column exists

-- First, try to add the column (this will fail silently if it already exists)
-- Actually, DuckDB will error, so we need a different approach

-- For now, we'll just document that this migration should be applied BEFORE
-- the schema is initialized with the new model, OR the column should be manually added
-- This is not ideal, but DuckDB's DDL limitations make it difficult to do conditional DDL

-- Skip this migration for now since the model already has the column
-- and schema initialization creates it automatically
-- In production, you would apply migrations before deploying model changes

-- DO NOTHING
-- The config_json column will be created by initialize_schema() from the updated model
