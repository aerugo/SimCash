-- Migration 002: Add config_json to simulations table
-- Purpose: Store complete simulation configuration for diagnostic frontend
-- Created: 2025-11-02
--
-- This enables the diagnostic dashboard to display full configuration details
-- including all agents, policies, and arrival configs without depending on
-- external YAML files.
--
-- Pattern: Mirrors simulation_checkpoints.config_json (already proven)

-- Add config_json column (nullable for backwards compatibility)
-- Idempotent: Uses IF NOT EXISTS to skip if column already exists
ALTER TABLE simulations ADD COLUMN IF NOT EXISTS config_json VARCHAR;

-- No index needed - config_json is only queried by primary key lookups
-- which already use the simulation_id index
