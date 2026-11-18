const STEPS = ["Applied", "In review", "Interview", "Result"];
const MESSAGES = [
  "Waiting for the company to reply",
  "Your application is being reviewed",
  "Prepare for your interview",
  "The company has shared a result",
];

export default function ApplicationProgress({ status = 0, onUpdate, updating = false }) {
  const current = Math.max(0, Math.min(STEPS.length - 1, Number(status) || 0));
  return <div className="application-progress-card">
    <span className="application-status-pill">Applied · {STEPS[current]}</span>
    <div className="application-progress-steps" role="list" aria-label={`Application status: ${STEPS[current]}`}>
      {STEPS.map((step, index) => <div key={step} role="listitem" className={`application-progress-step ${index < current ? "is-finished" : index === current ? "is-current" : "is-upcoming"}`}>
        <span className="application-progress-track" aria-hidden="true"/>
        <span className="application-progress-dot" aria-hidden="true"/>
        <span className="application-progress-label">{step}</span>
      </div>)}
    </div>
    <p className="application-progress-message">{MESSAGES[current]}</p>
    {onUpdate && <button type="button" className="application-progress-update" onClick={onUpdate} disabled={updating || current === STEPS.length - 1}>{updating ? "Saving…" : current === STEPS.length - 1 ? "Status complete" : "Update status"}</button>}
  </div>;
}
