import { useEffect, useState } from 'react';

type PlanSummary = {
  id: string;
  title: string;
};

type Plan = {
  id: string;
  text: string;
  review: {
    deadline_day: number | null;
    tasks: {
      id: string;
      name: string;
      owner: string | null;
      duration_days: number;
      depends_on: string[];
      quote: string;
    }[];
    findings: { title: string; detail: string; quote: string }[];
  };
  schedule: {
    schedule: { id: string; start_day: number; end_day: number }[];
    meets_deadline: boolean;
  };
};

export default function App() {
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [plan, setPlan] = useState<Plan | null>(null);

  useEffect(() => {
    fetch('/api/plans')
      .then((response) => response.json())
      .then((items: PlanSummary[]) => {
        setPlans(items);
        if (items.length > 0) setSelectedId(items[0].id);
      });
  }, []);

  useEffect(() => {
    setPlan(null);
    if (!selectedId) return;
    fetch(`/api/plans/${selectedId}`)
      .then((response) => response.json())
      .then(setPlan);
  }, [selectedId]);

  return (
    <>
      <label>
        Plan{' '}
        <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
          {plans.map((item) => (
            <option key={item.id} value={item.id}>{item.title}</option>
          ))}
        </select>
      </label>
      {plan && (
        <>
          <pre>{plan.text}</pre>
          <pre>{JSON.stringify(plan.review, null, 2)}</pre>
          <table>
            <thead>
              <tr><th>Name</th><th>Owner</th><th>Days</th><th>Start</th><th>End</th></tr>
            </thead>
            <tbody>
              {plan.review.tasks.map((task) => {
                const scheduled = plan.schedule.schedule.find((entry) => entry.id === task.id);
                return (
                  <tr key={task.id}>
                    <td>{task.name}</td>
                    <td>{task.owner}</td>
                    <td>{task.duration_days}</td>
                    <td>{scheduled?.start_day}</td>
                    <td>{scheduled?.end_day}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p>Meets deadline: {plan.schedule.meets_deadline ? 'yes' : 'no'}</p>
        </>
      )}
    </>
  );
}
