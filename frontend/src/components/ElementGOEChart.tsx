import { useState, useMemo } from "react";
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
  markers: string[];
  competition: string;
  date: string;
}

export default function ElementGOEChart({ elements }: Props) {
  // Collect unique element names
  const elementNames = useMemo(() => {
    const names = new Set<string>();
    elements.forEach((el) => {
      if (el.goe != null) names.add(el.element_name);
    });
    return Array.from(names).sort();
  }, [elements]);

  const [selected, setSelected] = useState<string>("");

  if (!elements || elements.length === 0) {
    return (
      <div className="flex items-center justify-center h-[280px] text-on-surface-variant text-sm font-body">
        Aucune donnée d'élément disponible
      </div>
    );
  }

  // Filter by selected element
  const filtered = selected
    ? elements.filter((el) => el.element_name === selected && el.goe != null)
    : elements.filter((el) => el.goe != null);

  const data: ChartEntry[] = filtered
    .sort((a, b) => {
      const dateA = a.competition_date ?? "";
      const dateB = b.competition_date ?? "";
      if (dateA !== dateB) return dateA < dateB ? -1 : 1;
      return a.element_name.localeCompare(b.element_name);
    })
    .map((el) => {
      const shortComp = el.competition_name
        ? el.competition_name.replace(/\s*\d{4}\s*-?\s*/, " ").trim()
        : "?";
      return {
        label: selected ? shortComp : `${el.element_name}`,
        goe: el.goe!,
        elementName: el.element_name,
        markers: el.markers ?? [],
        competition: el.competition_name ?? "?",
        date: el.competition_date ? el.competition_date.slice(0, 10) : "?",
      };
    });

  // Marker labels in French for the tooltip
  const MARKER_LABELS: Record<string, string> = {
    "*":  "annulé",
    "<<": "déclassé",
    "<":  "sous-rotation",
    "q":  "quart court",
    "e":  "carre incorrecte",
    "!":  "carre incertaine",
    "x":  "bonus 2e moitié",
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const entry: ChartEntry = payload[0].payload;
    // Filter out the "+" positional sentinel before display
    const displayMarkers = (entry.markers ?? []).filter((m) => m !== "+");
    const hasMarkers = displayMarkers.length > 0;
    return (
      <div className="bg-surface-container-lowest rounded-xl shadow-sm p-3 text-xs font-body min-w-[160px]">
        <p className="font-mono font-bold text-on-surface">
          {entry.elementName}
          {hasMarkers && (
            <span className="ml-1 font-normal text-[10px] text-on-surface-variant">
              {displayMarkers.join(" ")}
            </span>
          )}
        </p>
        {hasMarkers && (
          <div className="mt-1 flex flex-wrap gap-1">
            {displayMarkers.map((m) => (
              <span
                key={m}
                className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold font-mono
                  ${m === "x" ? "bg-primary/10 text-primary" :
                    m === "!" ? "bg-amber-50 text-amber-700" :
                    "bg-error/10 text-[#ba1a1a]"}`}
              >
                {m} · {MARKER_LABELS[m] ?? m}
              </span>
            ))}
          </div>
        )}
        <p className="text-on-surface-variant mt-1.5">{entry.competition}</p>
        <p className={`font-mono font-bold mt-1 ${entry.goe >= 0 ? "text-primary" : "text-[#ba1a1a]"}`}>
          GOE : {entry.goe >= 0 ? "+" : ""}{entry.goe.toFixed(2)}
        </p>
      </div>
    );
  };

  return (
    <div>
      <select
        className="bg-surface-container-high rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary w-full mb-4"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        <option value="">Tous les éléments</option>
        {elementNames.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>

      {data.length === 0 ? (
        <div className="flex items-center justify-center h-[240px] text-on-surface-variant text-sm font-body">
          Aucune donnée pour cet élément
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 32 }}>
            <CartesianGrid vertical={false} stroke="#e0e3e5" />
            <XAxis
              dataKey="label"
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
              {data.map((entry, index) => {
                const hasPenalty = entry.markers.some((m) =>
                  ["*", "<", "<<", "q", "e", "!"].includes(m)
                );
                return (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.goe >= 0 ? "#2e6385" : "#ba1a1a"}
                    fillOpacity={hasPenalty ? 0.45 : 0.85}
                  />
                );
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
