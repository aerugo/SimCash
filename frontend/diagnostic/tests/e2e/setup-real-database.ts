/**
 * Setup utility for e2e tests with real simulation database
 *
 * This script:
 * 1. Runs the 12-bank scenario simulation
 * 2. Creates a real database with transaction data
 * 3. Returns database path and simulation ID for tests
 */

import { execSync } from "child_process";
import { existsSync, mkdirSync, unlinkSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export interface SimulationSetup {
  dbPath: string;
  simulationId: string;
  cleanup: () => void;
}

/**
 * Run the 12-bank simulation and return setup details
 * Uses unique database file per test to avoid lock conflicts
 */
export async function setupRealDatabase(): Promise<SimulationSetup> {
  // Path to config file (from frontend/diagnostic to examples/configs)
  const configPath = join(
    __dirname,
    "../../../../examples/configs/12_bank_4_policy_comparison.yaml"
  );

  if (!existsSync(configPath)) {
    throw new Error(`Config file not found: ${configPath}`);
  }

  // Create database in a test directory with unique name per worker/test
  const testDbDir = join(__dirname, "../../../../api/test_databases");

  // Ensure test database directory exists
  if (!existsSync(testDbDir)) {
    mkdirSync(testDbDir, { recursive: true });
  }

  // Use timestamp + random to avoid conflicts between parallel tests
  const uniqueId = `${Date.now()}_${Math.random().toString(36).substring(7)}`;
  const dbPath = join(testDbDir, `e2e_test_${uniqueId}.db`);

  console.log("🔧 Running 12-bank simulation...");
  console.log(`   Config: ${configPath}`);
  console.log(`   Database: ${dbPath}`);

  // Run simulation with Python CLI using uv
  // This ensures we use the correct Python environment with the Rust module
  const cmd = [
    "uv",
    "run",
    "python",
    "-m",
    "payment_simulator.cli.main",
    "run",
    "--config",
    configPath,
    "--persist",
    "--db-path",
    dbPath,
    "--quiet",
    "--ticks",
    "100", // Just 100 ticks for faster testing
    "--seed",
    "42", // Fixed seed for determinism
  ].join(" ");

  const startTime = Date.now();

  try {
    const output = execSync(cmd, {
      cwd: join(__dirname, "../../../../api"),
      encoding: "utf-8",
      maxBuffer: 10 * 1024 * 1024, // 10MB buffer
    });

    const duration = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(`✅ Simulation completed in ${duration}s`);

    // Extract JSON from output (CLI may include non-JSON text like "Initializing...")
    // Find where JSON starts (first line with '{') and take everything after
    const lines = output.trim().split("\n");
    let jsonStartIndex = -1;
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].trim().startsWith("{")) {
        jsonStartIndex = i;
        break;
      }
    }

    if (jsonStartIndex === -1) {
      throw new Error(`No JSON output found. Output was:\n${output}`);
    }

    // Join all lines from JSON start onwards
    const jsonText = lines.slice(jsonStartIndex).join("\n");

    // Parse output to get simulation ID
    const result = JSON.parse(jsonText);
    const simulationId =
      result.simulation?.simulation_id || result.simulation_id;

    if (!simulationId) {
      throw new Error(`No simulation_id in output: ${jsonText}`);
    }

    console.log(`📊 Simulation ID: ${simulationId}`);

    return {
      dbPath,
      simulationId,
      cleanup: () => {
        // Delete the temporary database file
        try {
          if (existsSync(dbPath)) {
            unlinkSync(dbPath);
            console.log(`🧹 Cleaned up test database: ${dbPath}`);
          }
        } catch (error) {
          console.warn(`⚠️  Failed to cleanup database: ${error}`);
        }
      },
    };
  } catch (error) {
    console.error("❌ Simulation failed:", error);
    // Cleanup failed simulation database
    try {
      if (existsSync(dbPath)) {
        unlinkSync(dbPath);
      }
    } catch {
      // Ignore cleanup errors
    }
    throw error;
  }
}

/**
 * Start API server with the test database
 * Returns the API URL
 */
export function getApiUrl(): string {
  // In tests, the API should already be running via webServer config
  // This just returns the URL for reference
  return process.env.API_URL || "http://localhost:8000";
}
