const workflow = [
  'Input',
  'Image Quality',
  'CV + OCR + Layout',
  'Applicability Engine',
  'Rule Validation',
  'Inspector Review',
  'Final Report',
  'Analytics Hub',
];

const stack = [
  'React + Vite',
  'FastAPI',
  'OpenCV + PaddleOCR',
  'PostgreSQL',
  'Redis',
  'RBAC',
];

export default function App() {
  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">SAHILABEL</p>
          <h1>Legal Metrology Compliance Workflow</h1>
        </div>
        <button className="primary-btn">New Inspection</button>
      </header>

      <section className="panel">
        <h2>Target workflow</h2>
        <div className="flow-grid">
          {workflow.map((step) => (
            <div key={step} className="flow-step">
              {step}
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Technology stack</h2>
        <div className="stack-grid">
          {stack.map((item) => (
            <div key={item} className="stack-item">
              {item}
            </div>
          ))}
        </div>
      </section>

      <section className="panel compact">
        <h2>Phase 1 architecture alignment</h2>
        <ul>
          <li>Frontend scaffold for React + Vite</li>
          <li>Backend app structure for FastAPI</li>
          <li>RBAC/auth route placeholders</li>
          <li>Redis + PostgreSQL configuration scaffold</li>
          <li>Workflow-aligned inspection service</li>
        </ul>
      </section>
    </div>
  );
}
