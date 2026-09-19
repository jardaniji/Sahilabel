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
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  async function createInspection() {
    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      if (file) {
        formData.append('file', file, file.name);
      }
      formData.append('product_name', productName || 'Sample label');
      formData.append('image_count', String(imageCount));

      const response = await fetch('http://localhost:8000/api/v1/inspections/analyze', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      setResult({ ok: response.ok, status: response.status, data });
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
        <h2>Upload and analyze label</h2>
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

        <div className="form-row">
          <label>
            Image file
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
        </div>

        <button className="primary-btn" onClick={createInspection} disabled={loading}>
          {loading ? 'Analyzing…' : 'Analyze label'}
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
