/**
 * Global setup for e2e tests
 * Creates the test database and starts API server before Playwright tests
 */

import { setupRealDatabase } from "./setup-real-database";
import { writeFileSync, unlinkSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { spawn } from "child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

let apiServerProcess: any = null;

export default async function globalSetup() {
  console.log("🔧 Global setup: Cleaning up any existing API servers...");

  // Kill any existing API server on port 8000
  try {
    const { execSync } = await import("child_process");
    execSync("lsof -ti:8000 | xargs kill -9 2>/dev/null || true", {
      stdio: "ignore",
    });
    await new Promise((resolve) => setTimeout(resolve, 1000));
  } catch (error) {
    // Ignore errors - port might not be in use
  }

  console.log("🔧 Global setup: Creating test database...");

  // Run the 12-bank simulation and create test database
  const simulationSetup = await setupRealDatabase();

  // Set environment variable for API server to use
  process.env.PAYMENT_SIM_DB_PATH = simulationSetup.dbPath;

  console.log(`✅ Global setup complete:`);
  console.log(`   Database: ${simulationSetup.dbPath}`);
  console.log(`   Simulation ID: ${simulationSetup.simulationId}`);

  // Store simulation info for tests to access
  const setupInfoPath = join(__dirname, ".test-setup-info.json");
  writeFileSync(
    setupInfoPath,
    JSON.stringify(
      {
        dbPath: simulationSetup.dbPath,
        simulationId: simulationSetup.simulationId,
      },
      null,
      2
    )
  );

  // Start API server with the test database
  console.log("🚀 Starting API server...");
  const apiDir = join(__dirname, "../../../../api");

  apiServerProcess = spawn(
    "uv",
    [
      "run",
      "uvicorn",
      "payment_simulator.api.main:app",
      "--host",
      "0.0.0.0",
      "--port",
      "8000",
    ],
    {
      cwd: apiDir,
      env: {
        ...process.env,
        PAYMENT_SIM_DB_PATH: simulationSetup.dbPath,
      },
      stdio: "inherit",
    }
  );

  // Wait for API server to be ready
  console.log("⏳ Waiting for API server to start...");
  await waitForServer("http://localhost:8000/health", 30000);
  console.log("✅ API server ready");

  // Return a teardown function
  return async () => {
    console.log("🧹 Global teardown: Stopping API server...");
    if (apiServerProcess) {
      apiServerProcess.kill();
      // Wait a bit for graceful shutdown
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }

    console.log("🧹 Global teardown: Cleaning up test database...");
    if (simulationSetup?.cleanup) {
      simulationSetup.cleanup();
    }

    // Remove the setup info file
    try {
      unlinkSync(setupInfoPath);
    } catch (error) {
      // Ignore errors
    }
  };
}

async function waitForServer(url: string, timeout: number): Promise<void> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch (error) {
      // Server not ready yet, continue waiting
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(`Server at ${url} did not become ready within ${timeout}ms`);
}
