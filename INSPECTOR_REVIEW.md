## Inspector review dummy run

Run the dependency-free model:

```bash
python run_dummy_review.py
python -m unittest -v test_inspector_review.py test_review_store.py
```

The persisted review API is provided by `review_api.py`. To mount it in the root FastAPI app, add:

```python
from review_api import review_router
app.include_router(review_router)
```

Then use a bearer token from `/auth/login`:

```bash
curl -X POST http://localhost:8000/api/v1/inspections/demo-001/reviews \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"automated_decision":{"status":"REVIEW"},"inspector_decision":"CONFIRMED","reason":"Verified on package"}'
```
