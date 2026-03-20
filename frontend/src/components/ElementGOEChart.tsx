import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Element } from "../api/client";

interface Props {
  elements: Element[];
}

interface ChartEntry {
  label: string;
  goe: number;
  elementName: string;
  date: string;
}

export default function ElementGOEChart({ elements }: Props) {
  if (!elements || elements.length === 0) {
    return (
      <div className="flex items-center justify-center h-[280px] text-on-surface-variant text-sm font-body">
        Aucune donnée d'élément disponible
      </div>
    );
  }

  // Build flat list: one entry per element occurrence, sorted by date then element_name
  const data: ChartEntry[] = elements
    .filter((el) => el.goe != null)
    .sort((a, b) => {
      const dateA = a.competition_date ?? "";
      const dateB = b.competition_date ?? "";
      if (dateA !== dateB) return dateA < dateB ? -1 : 1;
      return a.element_name.localeCompare(b.element_name);
    })
    .map((el) => {
      const shortDate = el.competition_date
        ? el.competition_date.slice(0, 10)
        : (el.competition_name ?? "?");
      return {
        label: `${shortDate} · ${el.element_name}`,
        goe: el.goe!,
        elementName: el.element_name,
        date: shortDate,
      };
    });

  // X-axis ticks: show only the date part to avoid clutter, deduplicated by index
  const xTickFormatter = (_: string, index: number) => {
    const entry = data[index];
    if (!entry) return "";
    // Show date only for first occurrence of each date group
    const prevEntry = index > 0 ? data[index - 1] : null;
    if (!prevEntry || prevEntry.date !== entry.date) {
      return entry.date;
    }
    return "";
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const entry: ChartEntry = payload[0].payload;
    return (
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-3 text-xs font-body">
        <p className="font-mono font-bold text-on-surface">{entry.elementName}</p>
        <p className="text-on-surface-variant">{entry.date}</p>
        <p className={`font-mono font-bold mt-1 ${entry.goe >= 0 ? "text-primary" : "text-[#ba1a1a]"}`}>
          GOE : {entry.goe >= 0 ? "+" : ""}{entry.goe.toFixed(2)}
        </p>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 32 }}>
        <CartesianGrid vertical={false} stroke="#e0e3e5" />
        <XAxis
          dataKey="label"
          tickFormatter={xTickFormatter}
          tick={{ fontSize: 9, fontFamily: "Inter, sans-serif", fill: "#41484d" }}
          axisLine={false}
          tickLine={false}
          interval={0}
          angle={-40}
          textAnchor="end"
          height={60}
        />
        <YAxis
          tick={{ fontSize: 10, fontFamily: "monospace", fill: "#41484d" }}
          axisLine={false}
          tickLine={false}
          domain={["auto", "auto"]}
        />
        <ReferenceLine y={0} stroke="#e0e3e5" strokeWidth={1.5} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="goe" radius={[3, 3, 0, 0]}>
          {data.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={entry.goe >= 0 ? "#2e6385" : "#ba1a1a"}
              fillOpacity={0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
