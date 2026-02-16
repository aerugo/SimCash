import type { SimEvent } from '../types';
import { EventLog } from '../components/EventLog';

export function EventsView({ events }: { events: SimEvent[] }) {
  return (
    <div>
      <h2 className="text-xl font-bold mb-4">📋 Event Log</h2>
      <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5">
        <EventLog events={events} fullPage />
      </div>
    </div>
  );
}
