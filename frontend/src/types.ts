export type Task = {
  id: string;
  name: string;
  owner: string | null;
  duration_days: number;
  depends_on: string[];
  quote: string;
};

export type Finding = {
  title: string;
  detail: string;
  quote: string | null;
  severity?: 'high' | 'medium' | 'low';
};

export type Review = { deadline_day: number | null; tasks: Task[]; findings: Finding[] };

export type Bound = { day: number; kind: 'chain' | 'owner' | 'empty'; tasks: string[]; owner: string | null };

export type Schedule = {
  status: 'scheduled' | 'cycle';
  schedule: { id: string; start_day: number; end_day: number }[];
  end_day: number | null;
  deadline_day: number | null;
  meets_deadline: boolean | null;
  days_late: number | null;
  cycle: string[];
  proof?: { optimal: boolean; lower_bound: Bound; driving_chain: string[]; owner_days: Record<string, number> };
};

export type Plan = { id: string; text: string; review: Review | null; schedule: Schedule | null };
