## Final inspector-review model

The model is integrated into the root FastAPI app on `main`.

### Model guarantees

- `automated_decision` is deep-copied and never overwritten.
- `inspector_decision` is one of `CONFIRMED`, `OVERRIDDEN`, or `PENDING`.
- `CONFIRMED` and `OVERRIDDEN` require a non-empty reason.
- reviewer identity comes from the authenticated JWT user.
- every review is appended to SQLite audit history.
- the latest review is exposed as the final decision while the automated result remains available.

### Local run

```bash
python -m pip install -r requirements.txt
python run_dummy_review.py
python -m unittest -v test_inspector_review.py test_review_store.py
uvicorn main:app --reload
```

Login:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=inspector&password=inspect123'
```

Submit a review using the returned token:

```bash
curl -X POST http://localhost:8000/api/v1/inspections/demo-001/reviews \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"automated_decision":{"status":"REVIEW"},"inspector_decision":"CONFIRMED","reason":"Verified on package"}'
```

Read review history and the latest final decision:

```bash
curl http://localhost:8000/api/v1/inspections/demo-001/reviews \
  -H 'Authorization: Bearer YOUR_TOKEN'
curl http://localhost:8000/api/v1/inspections/demo-001/final-decision \
  -H 'Authorization: Bearer YOUR_TOKEN'
```
