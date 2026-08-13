## Summary
<!-- One theme per PR. Link the issue. -->

Closes #

## Theme
- [ ] A tests / fixtures / seed
- [ ] B CI
- [ ] C Alembic
- [ ] D security (hashing, uploads, rate limit)
- [ ] E retention purge
- [ ] F docs
- [ ] G monitoring
- [ ] H SDK / RAG / sessions

## Test plan
- [ ] `cd backend && PYTHONPATH=. pytest tests/ -v`
- [ ] New or updated tests included
- [ ] Public APIs unchanged, or migration notes added

## Security / data
- [ ] No plaintext secrets
- [ ] Migrations are backward compatible (add columns, do not drop yet)
