import { useEffect, useMemo, useRef, useState } from 'react';
import { locateQuote } from './quotes';
import type { Finding, Plan, Schedule, Task } from './types';

type PlanSummary = { id: string; title: string };

const SEVERITY_LABEL = { high: 'Important', medium: 'Ask before sign-off', low: 'Minor' } as const;

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

export default function App() {
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    fetch('/api/plans')
      .then((r) => r.json())
      .then((items: PlanSummary[]) => {
        setPlans(items);
        const fromHash = decodeURIComponent(window.location.hash.slice(1));
        if (items.some((p) => p.id === fromHash)) setSelectedId(fromHash);
        else if (items.length > 0) setSelectedId(items[0].id);
      })
      .catch(() => setLoadError('The plans could not be loaded. Check that the server is running.'));
  }, []);

  useEffect(() => {
    setPlan(null);
    if (!selectedId) return;
    window.history.replaceState(null, '', `#${selectedId}`);
    fetch(`/api/plans/${selectedId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setPlan)
      .catch(() => setLoadError('This plan could not be loaded.'));
  }, [selectedId]);

  return (
    <div className="app">
      <header className="topbar">
        <span className="logo" aria-hidden>
          ◐
        </span>
        <span className="product">Plan review</span>
        <nav className="tabs" aria-label="Plans">
          {plans.map((p) => (
            <button key={p.id} className={p.id === selectedId ? 'tab current' : 'tab'} onClick={() => setSelectedId(p.id)}>
              {p.title.replace(/^Pellerby /, '')}
            </button>
          ))}
        </nav>
      </header>
      {loadError && <p className="banner warn">{loadError}</p>}
      {plan && <PlanView key={plan.id} plan={plan} title={plans.find((p) => p.id === plan.id)?.title ?? plan.id} />}
    </div>
  );
}

function PlanView({ plan, title }: { plan: Plan; title: string }) {
  const review = plan.review;
  const [tasks, setTasks] = useState<Task[]>(review?.tasks ?? []);
  const [deadline, setDeadline] = useState<number | null>(review?.deadline_day ?? null);
  const [schedule, setSchedule] = useState<Schedule | null>(plan.schedule);
  const [problems, setProblems] = useState<string[]>([]);
  const [activeQuote, setActiveQuote] = useState<string | null>(null);
  const edited = JSON.stringify(tasks) !== JSON.stringify(review?.tasks ?? []) || deadline !== (review?.deadline_day ?? null);

  // Re-schedule whenever she changes something. The server is the one source of truth for the schedule.
  useEffect(() => {
    if (!edited) {
      setSchedule(plan.schedule);
      setProblems([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetch('/api/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tasks, deadline_day: deadline ?? 0 }),
        signal: controller.signal,
      })
        .then(async (r) => {
          const body = await r.json();
          if (r.ok) {
            setSchedule(body);
            setProblems([]);
          } else {
            setProblems(body.problems ?? [body.error ?? 'The change could not be scheduled.']);
          }
        })
        .catch((e) => {
          if (e.name !== 'AbortError') setProblems(['The schedule could not be updated. Check your connection.']);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [tasks, deadline, edited, plan.schedule]);

  if (!review || !schedule) {
    return (
      <main className="layout">
        <section className="card">
          <h1 className="title">{title}</h1>
          <p className="muted">This plan has not been reviewed yet.</p>
        </section>
      </main>
    );
  }

  const reset = () => {
    setTasks(review.tasks);
    setDeadline(review.deadline_day);
  };

  return (
    <main className="layout">
      <div className="column">
        <h1 className="title">{title}</h1>
        <Verdict
          schedule={schedule}
          original={plan.schedule}
          deadline={deadline}
          tasks={tasks}
          edited={edited}
          onReset={reset}
          onDeadline={setDeadline}
        />
        {problems.length > 0 && (
          <div className="banner warn" role="alert">
            {problems.map((p) => (
              <div key={p}>{p}</div>
            ))}
          </div>
        )}
        <Findings findings={review.findings} activeQuote={activeQuote} onQuote={setActiveQuote} />
        <TaskTable
          tasks={tasks}
          original={review.tasks}
          schedule={schedule}
          deadline={deadline}
          activeQuote={activeQuote}
          onQuote={setActiveQuote}
          onChange={setTasks}
        />
      </div>
      <PlanText text={plan.text} activeQuote={activeQuote} />
    </main>
  );
}

function Verdict(props: {
  schedule: Schedule;
  original: Schedule | null;
  deadline: number | null;
  tasks: Task[];
  edited: boolean;
  onReset: () => void;
  onDeadline: (d: number | null) => void;
}) {
  const { schedule, original, deadline, tasks, edited } = props;
  const names = Object.fromEntries(tasks.map((t) => [t.id, t.name]));

  let headline: string;
  let tone: 'ok' | 'warn' | 'neutral';
  let facts: string[] = [];
  if (schedule.status === 'cycle') {
    headline = 'Cannot be scheduled: tasks wait on each other in a circle';
    tone = 'warn';
  } else {
    const end = schedule.end_day ?? 0;
    if (deadline === null) {
      headline = `Finishes on day ${end} at the earliest`;
      tone = 'neutral';
      facts = ['The plan gives no clear deadline'];
    } else if (end <= deadline) {
      headline = 'Can make its date';
      tone = 'ok';
      facts = [`Earliest finish day ${end}`, `deadline day ${deadline}`, `${plural(deadline - end, 'day')} to spare`];
    } else {
      headline = `Misses its date by ${plural(end - deadline, 'day')}`;
      tone = 'warn';
      facts = [`Earliest finish day ${end}`, `deadline day ${deadline}`];
    }
  }

  const proof = schedule.proof;
  const bound = proof?.lower_bound;
  const end = schedule.end_day ?? 0;

  return (
    <section className={`card verdict ${tone}`} aria-live="polite">
      <div className="section-label">Can it make its date?</div>
      <h2 className="headline">{headline}</h2>
      {facts.length > 0 && <p className="meta">{facts.join(' · ')}</p>}

      {schedule.status === 'cycle' && (
        <p className="why">
          {schedule.cycle.map((id) => names[id] ?? id).join(' → ')} → back to the start. Ask the committee which of these
          really has to come first, then correct it in the task list below.
        </p>
      )}

      {schedule.status === 'scheduled' && bound && proof && (
        <div className="why">
          {bound.kind === 'owner' && bound.day === end && (
            <p>
              It cannot finish sooner: <strong>{bound.owner}</strong> alone has {bound.day} days of work, and one person does one
              task at a time.
            </p>
          )}
          {bound.kind === 'chain' && bound.day === end && (
            <p>It cannot finish sooner: these tasks have to happen one after another and add up to {bound.day} days.</p>
          )}
          {bound.day < end && (
            <p>
              {proof.optimal
                ? `Every possible order of the tasks was checked: none finishes before day ${end}. Tasks waiting on each other and on the same people leave gaps that cannot be closed.`
                : `This is the best schedule found in the time allowed. It may be possible to finish a little sooner.`}
            </p>
          )}
          {proof.driving_chain.length > 0 && (
            <>
              <div className="section-label">What sets the date</div>
              <ol className="chain">
                {proof.driving_chain.map((id) => {
                  const t = tasks.find((x) => x.id === id);
                  return (
                    <li key={id}>
                      {t?.name ?? id}
                      <span className="muted">
                        {' '}
                        · {t?.owner ?? 'no owner'} · {t?.duration_days}{'\u00a0'}days
                      </span>
                    </li>
                  );
                })}
              </ol>
            </>
          )}
          {Object.keys(proof.owner_days).length > 0 && (
            <p className="meta">
              Days of work per person:{' '}
              {Object.entries(proof.owner_days)
                .sort((a, b) => b[1] - a[1])
                .map(([o, d]) => `${o} ${d}`)
                .join(' · ')}
            </p>
          )}
        </div>
      )}

      <div className="verdict-foot">
        <label className="deadline">
          Deadline day{' '}
          <input
            type="number"
            min={0}
            value={deadline ?? ''}
            placeholder="none"
            onChange={(e) => props.onDeadline(e.target.value === '' ? null : Math.max(0, Math.round(Number(e.target.value))))}
          />
        </label>
        {edited && (
          <span className="changes">
            <span>
              Your changes:{' '}
              {original?.status === 'cycle' ? 'was a circle' : `was day ${original?.end_day}`}
              {', now '}
              {schedule.status === 'cycle' ? 'a circle' : `day ${schedule.end_day}`}
            </span>
            <button className="quiet" onClick={props.onReset}>
              ↺ Back to the review
            </button>
          </span>
        )}
      </div>
    </section>
  );
}

function QuoteButton({ quote, active, onQuote }: { quote: string | null; active: boolean; onQuote: (q: string | null) => void }) {
  if (!quote) return <span className="muted small">Not stated in the plan</span>;
  return (
    <button className={active ? 'quote active' : 'quote'} onClick={() => onQuote(active ? null : quote)} title="Show in the plan">
      “{quote}”
    </button>
  );
}

function Findings({ findings, activeQuote, onQuote }: { findings: Finding[]; activeQuote: string | null; onQuote: (q: string | null) => void }) {
  const [showMinor, setShowMinor] = useState(false);
  const sev = (f: Finding) => f.severity ?? 'medium';
  const counts = { high: 0, medium: 0, low: 0 };
  findings.forEach((f) => counts[sev(f)]++);
  const shown = findings.filter((f) => showMinor || sev(f) !== 'low');

  return (
    <section className="card">
      <div className="section-head">
        <h2 className="subtitle">What to raise with the committee</h2>
        <span className="meta">
          {findings.length === 0
            ? 'Nothing found'
            : [counts.high && `${counts.high} important`, counts.medium && `${counts.medium} to ask`, counts.low && `${counts.low} minor`]
                .filter(Boolean)
                .join(' · ')}
        </span>
      </div>
      <ul className="findings">
        {shown.map((f, i) => (
          <li key={i} className={`finding ${sev(f)}`}>
            <div className="finding-title">
              <span className={`sev ${sev(f)}`}>{SEVERITY_LABEL[sev(f)]}</span>
              {f.title}
            </div>
            <p>{f.detail}</p>
            <QuoteButton quote={f.quote} active={activeQuote === f.quote} onQuote={onQuote} />
          </li>
        ))}
      </ul>
      {counts.low > 0 && (
        <button className="quiet" onClick={() => setShowMinor(!showMinor)}>
          {showMinor ? 'Hide minor points' : `Show ${plural(counts.low, 'minor point')}`}
        </button>
      )}
    </section>
  );
}

function TaskTable(props: {
  tasks: Task[];
  original: Task[];
  schedule: Schedule;
  deadline: number | null;
  activeQuote: string | null;
  onQuote: (q: string | null) => void;
  onChange: (tasks: Task[]) => void;
}) {
  const { tasks, original, schedule, deadline } = props;
  const slots = Object.fromEntries(schedule.schedule.map((s) => [s.id, s]));
  const span = Math.max(1, schedule.end_day ?? 0, deadline ?? 0);
  const driving = new Set(schedule.proof?.driving_chain ?? []);
  const inCycle = new Set(schedule.cycle);
  const before = Object.fromEntries(original.map((t) => [t.id, t]));

  const update = (id: string, patch: Partial<Task>) => props.onChange(tasks.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  const remove = (id: string) =>
    props.onChange(tasks.filter((t) => t.id !== id).map((t) => ({ ...t, depends_on: t.depends_on.filter((d) => d !== id) })));
  const add = () => {
    let n = tasks.length + 1;
    while (tasks.some((t) => t.id === `T${n}`)) n++;
    props.onChange([...tasks, { id: `T${n}`, name: 'New task', owner: null, duration_days: 1, depends_on: [], quote: '' }]);
  };
  const changed = (t: Task, field: keyof Task) => before[t.id] && JSON.stringify(before[t.id][field]) !== JSON.stringify(t[field]);

  return (
    <section className="card">
      <div className="section-head">
        <h2 className="subtitle">Tasks</h2>
        <span className="meta">Change anything that is wrong; the date above updates.</span>
      </div>
      <div className="table-wrap">
        <table className="tasks">
          <thead>
            <tr>
              <th>Task</th>
              <th>Who</th>
              <th className="num">Days</th>
              <th>Waits for</th>
              <th className="timeline-head">
                Day 0 – {span}
              </th>
              <th aria-label="Remove" />
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => {
              const slot = slots[t.id];
              const late = slot && deadline !== null && slot.end_day > deadline;
              return (
                <tr key={t.id} className={inCycle.has(t.id) ? 'cycle' : ''}>
                  <td className="name">
                    <textarea
                      rows={1}
                      className={changed(t, 'name') || !before[t.id] ? 'edited' : ''}
                      value={t.name}
                      onChange={(e) => update(t.id, { name: e.target.value })}
                      aria-label="Task name"
                    />
                    {t.quote ? (
                      <button className={props.activeQuote === t.quote ? 'source active' : 'source'} onClick={() => props.onQuote(props.activeQuote === t.quote ? null : t.quote)}>
                        In the plan
                      </button>
                    ) : (
                      <span className="source muted">Added by you</span>
                    )}
                  </td>
                  <td>
                    <input
                      className={changed(t, 'owner') ? 'edited owner' : 'owner'}
                      value={t.owner ?? ''}
                      placeholder="Nobody"
                      onChange={(e) => update(t.id, { owner: e.target.value.trim() === '' ? null : e.target.value })}
                      aria-label="Who"
                    />
                  </td>
                  <td className="num">
                    <input
                      className={changed(t, 'duration_days') ? 'edited days' : 'days'}
                      type="number"
                      min={1}
                      value={t.duration_days}
                      onChange={(e) => update(t.id, { duration_days: Math.max(1, Math.round(Number(e.target.value) || 1)) })}
                      aria-label="Days"
                    />
                  </td>
                  <td>
                    <DependsOn task={t} tasks={tasks} edited={!!changed(t, 'depends_on')} onChange={(deps) => update(t.id, { depends_on: deps })} />
                  </td>
                  <td className="timeline">
                    {slot && (
                      <div className="track" title={`Day ${slot.start_day} to day ${slot.end_day}`}>
                        {deadline !== null && <div className="deadline-line" style={{ left: `${(deadline / span) * 100}%` }} />}
                        <div
                          className={`bar ${late ? 'late' : driving.has(t.id) ? 'driving' : ''}`}
                          style={{ left: `${(slot.start_day / span) * 100}%`, width: `${((slot.end_day - slot.start_day) / span) * 100}%` }}
                        />
                      </div>
                    )}
                    {slot && (
                      <span className="meta tabular">
                        {slot.start_day}–{slot.end_day}
                      </span>
                    )}
                  </td>
                  <td>
                    <button className="quiet icon" onClick={() => remove(t.id)} title="Remove this task" aria-label={`Remove ${t.name}`}>
                      ×
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="legend meta">
        <span><i className="bar driving" /> sets the date</span>
        <span><i className="bar late" /> after the deadline</span>
        <span><i className="edited-swatch" /> changed by you</span>
        <button className="quiet" onClick={add}>
          + Add a task
        </button>
      </div>
    </section>
  );
}

function DependsOn({ task, tasks, edited, onChange }: { task: Task; tasks: Task[]; edited: boolean; onChange: (deps: string[]) => void }) {
  const names = Object.fromEntries(tasks.map((t) => [t.id, t.name]));
  const options = tasks.filter((t) => t.id !== task.id && !task.depends_on.includes(t.id));
  return (
    <div className={edited ? 'deps edited' : 'deps'}>
      {task.depends_on.map((d) => (
        <span key={d} className="chip">
          {names[d] ?? d}
          <button onClick={() => onChange(task.depends_on.filter((x) => x !== d))} aria-label={`Stop waiting for ${names[d] ?? d}`}>
            ×
          </button>
        </span>
      ))}
      {options.length > 0 && (
        <select value="" onChange={(e) => e.target.value && onChange([...task.depends_on, e.target.value])} aria-label="Add a task it waits for">
          <option value="">+ add</option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}

function PlanText({ text, activeQuote }: { text: string; activeQuote: string | null }) {
  const markRef = useRef<HTMLElement>(null);
  const range = useMemo(() => (activeQuote ? locateQuote(text, activeQuote) : null), [text, activeQuote]);

  useEffect(() => {
    markRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [range]);

  return (
    <aside className="card plan">
      <div className="section-label">The plan as sent</div>
      {activeQuote && !range && <p className="banner warn">This quote could not be found in the plan.</p>}
      <div className="plan-text">
        {range ? (
          <>
            {text.slice(0, range[0])}
            <mark ref={markRef}>{text.slice(range[0], range[1])}</mark>
            {text.slice(range[1])}
          </>
        ) : (
          text
        )}
      </div>
    </aside>
  );
}
