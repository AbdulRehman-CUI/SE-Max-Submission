import { useCallback, useState } from "react";
import { Sparkles } from "lucide-react";
import { analytics } from "../api";
import { InsightsContent } from "../components/Finance";
import {
  ErrorMessage,
  Loading,
  MonthPicker,
  PageHeading,
} from "../components/ui";
import { useResource } from "../hooks/useResource";
import { monthLabel, today } from "../lib/format";

export default function InsightsPage() {
  const [period, setPeriod] = useState(today().slice(0, 7));
  const resource = useResource(
    useCallback(() => analytics.insights(period), [period]),
  );
  return (
    <>
      <PageHeading
        eyebrow="A LITTLE PERSPECTIVE"
        title="Financial insights"
        description="Observations based on your recorded spending, budgets and trends."
      >
        <MonthPicker value={period} onChange={setPeriod} />
      </PageHeading>
      <section className="card panel">
        <div className="section-heading">
          <h2>
            <Sparkles size={20} />
            {monthLabel(period)}
          </h2>
        </div>
        {resource.loading ? (
          <Loading />
        ) : resource.error ? (
          <ErrorMessage error={resource.error} retry={resource.reload} />
        ) : (
          resource.data && <InsightsContent data={resource.data} />
        )}
      </section>
      <p className="page-note">
        These observations are for personal reflection and are not professional
        financial advice.
      </p>
    </>
  );
}
