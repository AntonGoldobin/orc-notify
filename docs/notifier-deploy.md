# orc-notify deploy notes

Operational guidance for running orc-notify in production.

## Phase 1: topics + topic_keys + messages

Phase 1 adds three tables and four URL surfaces — alongside the existing
event-fanout API. No existing endpoint changes.

### Migration

Alembic handles the schema. Dockerfile CMD is `alembic upgrade head && uvicorn`,
so the new migration `0002_topics` runs on every container start. Manual
recovery if a deploy partially applied:

```bash
ssh root@<vps>
docker exec srv-captain--notifier alembic upgrade head
docker exec srv-captain--notifier alembic downgrade base   # rolls back BOTH 0001 and 0002
docker exec srv-captain--notifier alembic upgrade head     # rebuild
```

### Topic key rotation

Topic keys are HMAC credentials. Treat the raw `secret` like an API token —
returned exactly once at create / PATCH. To rotate:

```bash
curl -b cookies.txt -X PATCH https://orc-notify.orc.golden-antelope.ru/api/topics/alerts/keys/<id> \
  -H 'Content-Type: application/json' \
  -d '{"name": "renamed"}'
```

The new secret is in the response. Update all senders before deleting the old
key (delete = cascade-deletes the key only; messages stay).

### TTL pruning

`app/services/prune.py` runs an asyncio task every 3600s. It honours per-topic
`retention_days` (1-365). Default 7 days. Delete a message manually:

```sql
DELETE FROM messages WHERE id = '<message_id>';
```

### Multi-instance note

Single-instance only. The in-process pubsub (`app/services/pubsub_topics.py`)
does NOT sync across workers. If you scale `instanceCount > 1`, subscribers
on different instances miss messages from publishers on the other. Mitigation
in Phase 2: replace with Postgres LISTEN/NOTIFY.

### Smoke verification

```bash
bash scripts/smoke-phase-01.sh https://orc-notify.orc.golden-antelope.ru
```

Requires a running backend. Exits 0 on full publish-subscribe round-trip.
