import { useState } from 'react';

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

const stack = ['React + Vite', 'FastAPI', 'OpenCV + PaddleOCR', 'PostgreSQL', 'Redis', 'RBAC'];

export default function App() {
  const [productName, setProductName] = useState('Sample label');
  const [imageCount, setImageCount] = useState(2);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  async function createInspection() {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/v1/inspections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_name: productName, image_count: imageCount, source: 'upload' }),
      });

      const data = await response.json();
      setResult({ ok: response.ok, data });
    } catch (error) {
      setResult({ ok: false, data: { detail: String(error) } });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">SAHILABEL</p>
          <h1>Legal Metrology Compliance Workflow</h1>
        </div>
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
        <h2>Create a demo inspection</h2>
        <div className="form-row">
          <label>
            Product name
            <input value={productName} onChange={(e) => setProductName(e.target.value)} />
          </label>
          <label>
            Image count
            <input
              type="number"
              min="1"
              max="8"
              value={imageCount}
              onChange={(e) => setImageCount(Number(e.target.value) || 1)}
            />
          </label>
        </div>

        <button className="primary-btn" onClick={createInspection} disabled={loading}>
          {loading ? 'Creating…' : 'Create inspection'}
        </button>

        {result && (
          <pre className="result-box">
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </section>
    </div>
  );
}
