# Payment Simulator - Diagnostic Client

A React-based diagnostic dashboard for analyzing and visualizing payment simulation results. This tool provides deep insights into agent behavior, transaction flows, settlement patterns, and system performance.

## Overview

The Diagnostic Client is a web application that connects to the Payment Simulator API to:
- Browse historical simulation runs
- Analyze agent settlement strategies and liquidity management
- Trace individual transaction lifecycles
- Visualize collateral events and balance fluctuations
- Inspect settlement rates, costs, and performance metrics

## Architecture

```
┌─────────────────────────────────────┐
│  React Frontend (Vite + TypeScript) │
│  - Simulation list & dashboards     │
│  - Agent detail views               │
│  - Transaction tracing              │
│  - Event timeline visualization     │
└──────────────┬──────────────────────┘
               │ HTTP REST API
┌──────────────▼──────────────────────┐
│  Python FastAPI Backend (/api)      │
│  - SQLite database queries          │
│  - Simulation metadata              │
│  - Agent & transaction analytics    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  SQLite Database                    │
│  - Simulation results               │
│  - Transaction history              │
│  - Agent metrics                    │
└─────────────────────────────────────┘
```

## Prerequisites

- **Node.js** 18+ and **Bun** (for frontend)
- **Python** 3.13+ and **uv** (for backend API)
- Completed simulation runs (stored in `simulation_data.db`)

## Quick Start

### 1. Start the Backend API

The diagnostic client requires the Payment Simulator API to be running.

```bash
# From the repository root
cd api

# Start the API server with the simulation database (use absolute path to avoid issues)
PAYMENT_SIM_DB_PATH="$PWD/../simulation_data.db" uv run uvicorn payment_simulator.api.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

**API Documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 2. Start the Frontend

```bash
# From the repository root
cd frontend/diagnostic

# Install dependencies (first time only)
bun install

# Start the development server
bun run dev
```

The dashboard will be available at `http://localhost:5173`

### 3. Open the Dashboard

Navigate to http://localhost:5173 in your browser. You should see the simulation list page.

## Using the Dashboard

### Simulation List

The home page displays all completed simulation runs from the database.

**Features:**
- View simulation metadata (ID, creation date, configuration)
- See summary metrics (transaction count, settlement rate, total cost)
- Click any simulation to open its dashboard

### Simulation Dashboard

The main dashboard for analyzing a specific simulation run.

**Metrics Displayed:**
- **Settlement Rate**: Percentage of transactions successfully settled
- **Total Cost**: Aggregate delay penalties and fees (in cents)
- **Total Transactions**: Count of all payment attempts
- **Performance**: Ticks processed and execution speed

**Configuration Details:**
- Number of simulation days and ticks per day
- RNG seed (for reproducibility)
- Agent list with opening balances and credit limits

**Navigation Options:**
- View detailed timeline of all events
- Click on any agent to see individual performance
- Navigate back to simulation list

### Agent Detail View

Deep dive into a specific agent's (bank's) behavior and performance.

**Summary Metrics:**
- Total sent/received/settled/dropped transactions
- Average balance and peak overdraft
- Total costs incurred
- Credit limit utilization

**Daily Metrics Table:**
- Day-by-day balance evolution
- Opening/closing balances
- Min/max balance during the day
- Transaction counts (sent/received)
- Daily costs

**Collateral Events:**
- Deposits and withdrawals
- Tick-level timestamps
- Amount tracking

### Event Timeline

Chronological view of all system events during the simulation.

**Event Types:**
- **Arrival**: New transaction enters the system
- **Settlement**: Transaction successfully settled
- **Drop**: Transaction dropped due to deadline or constraints
- **PolicyHold**: Transaction held by agent's policy
- **LSMAttempt**: Liquidity-saving mechanism attempted

**Features:**
- Color-coded event badges
- Transaction details (sender, receiver, amount, priority)
- Links to transaction detail pages
- Pagination for large simulations

### Transaction Detail

Complete lifecycle view of a single transaction.

**Information Displayed:**
- Sender and receiver agent IDs
- Amount and priority
- Arrival, deadline, and settlement ticks
- Status (settled, pending, dropped, split, partially_settled)
- Amount settled vs. requested
- Delay costs and penalties

**Event Timeline:**
- Chronological list of all events affecting this transaction
- Event-specific details and metadata

**Related Transactions:**
- View split parts (if transaction was divided)
- Track parent/child relationships

## Development

### Project Structure

```
frontend/diagnostic/
├── src/
│   ├── components/          # Reusable UI components
│   ├── hooks/               # React Query hooks for API calls
│   ├── pages/               # Page components (routes)
│   ├── types/               # TypeScript type definitions
│   ├── utils/               # Utility functions (currency formatting, etc.)
│   ├── App.tsx              # Main app component with routing
│   └── main.tsx             # Application entry point
├── tests/
│   ├── e2e/                 # Playwright end-to-end tests
│   ├── component/           # Component tests (future)
│   └── unit/                # Unit tests (future)
├── public/                  # Static assets
└── vite.config.ts           # Vite configuration
```

### Running Tests

**End-to-End Tests (Playwright):**
```bash
# Run all E2E tests across browsers
bun test:e2e

# Run E2E tests in headed mode (see browser)
bun run playwright test --headed

# Run specific test file
bun run playwright test tests/e2e/simulation-flow.spec.ts

# View test report
bunx playwright show-report
```

**Unit/Component Tests (Vitest):**
```bash
# Run unit tests
bun run test

# Run with coverage
bun run test:coverage

# Watch mode
bun run test:watch
```

### Code Quality

```bash
# Type checking
bun run typecheck

# Linting
bun run lint

# Build for production
bun run build
```

## Configuration

### API Proxy

The frontend is configured to proxy `/api/*` requests to `http://localhost:8000` in development (see [vite.config.ts](vite.config.ts)).

For production deployment, update the API base URL in the fetch calls or use environment variables.

### Database Path

The backend API requires the `PAYMENT_SIM_DB_PATH` environment variable to point to your simulation database:

```bash
# Point to a specific database (always use absolute paths!)
PAYMENT_SIM_DB_PATH=/absolute/path/to/simulation_data.db uv run uvicorn payment_simulator.api.main:app

# Or use $PWD for current directory
PAYMENT_SIM_DB_PATH="$PWD/simulation_data.db" uv run uvicorn payment_simulator.api.main:app
```

## API Endpoints

The diagnostic client uses these API endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/simulations` | List all simulations |
| `GET /api/simulations/{sim_id}` | Get simulation metadata |
| `GET /api/simulations/{sim_id}/agents` | List agents in simulation |
| `GET /api/simulations/{sim_id}/agents/{agent_id}/timeline` | Get agent metrics |
| `GET /api/simulations/{sim_id}/events` | Get event timeline (paginated) |
| `GET /api/simulations/{sim_id}/transactions/{tx_id}/lifecycle` | Get transaction details |

See the [API Documentation](../../docs/api.md) for complete endpoint specifications.

## Troubleshooting

### "No simulations found"

**Problem:** The simulation list page shows "No simulations available."

**Solutions:**
1. Verify the API is running at `http://localhost:8000`
2. Check that `PAYMENT_SIM_DB_PATH` points to a valid database with completed simulations
3. Run a simulation to populate the database:
   ```bash
   cd api
   uv run python -m payment_simulator.cli run --config ../sim_config_example.yaml
   ```

### API connection errors

**Problem:** Dashboard shows network errors or fails to load data.

**Solutions:**
1. Ensure the API server is running (check `http://localhost:8000/docs`)
2. Verify the proxy configuration in `vite.config.ts`
3. Check browser console for CORS or network errors
4. Try accessing API endpoints directly (e.g., `http://localhost:8000/api/simulations`)

### Test failures

**Problem:** E2E tests fail with timeout or element not found errors.

**Solutions:**
1. Ensure both API and frontend are running before tests
2. Check that test database has expected data
3. Run tests in headed mode to see what's happening:
   ```bash
   bun run playwright test --headed
   ```
4. Update Playwright browsers:
   ```bash
   bunx playwright install
   ```

## Performance Considerations

- **Large Simulations**: Simulations with >10,000 transactions may experience slower load times on the event timeline. Use pagination controls to navigate.
- **Browser Limits**: Chrome/Firefox handle up to 50,000 DOM nodes well. Webkit may be slower on very large datasets.
- **API Response Time**: Complex queries (agent timelines with daily metrics) may take 100-500ms for large simulations.

## Future Enhancements

Planned features for future releases:

- [ ] Real-time simulation monitoring (WebSocket updates)
- [ ] Advanced filtering and search
- [ ] Comparison views (compare multiple simulations)
- [ ] Export to CSV/JSON
- [ ] Custom metric dashboards
- [ ] Network graph visualization of transaction flows
- [ ] Policy configuration editor

## Contributing

When adding new features:

1. **Follow TDD**: Write E2E tests first, then implement features
2. **Type Safety**: All API responses should have TypeScript interfaces in `src/types/api.ts`
3. **Accessibility**: Use semantic HTML and ARIA roles
4. **Responsive Design**: Test on mobile, tablet, and desktop viewports
5. **Cross-Browser**: Verify in Chromium, Firefox, and WebKit

## License

This project is part of the Payment Simulator system. See the main repository [README](../../README.md) for license information.

## Support

For issues, questions, or feature requests:
- Check the [main documentation](../../docs/)
- Review [architecture diagrams](../../docs/architecture.md)
- Open an issue on the repository

---

**Last Updated:** 2025-11-02
**Version:** 1.0.0 (Initial Release)
