#!/usr/bin/env python3
"""
Quick verification that the API endpoint works end-to-end.

Tests the complete flow:
1. Create database with events
2. Start FastAPI app with test database
3. Query via HTTP endpoint
4. Verify response structure and filtering

This bypasses pytest environment issues to directly verify functionality.
