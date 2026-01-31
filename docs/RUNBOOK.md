# AI Video Factory - Operational Runbook

## Quick Reference

### Service URLs (Development)
| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Inngest Dashboard | http://localhost:8288 |

### Health Check
```bash
# Quick health check
curl http://localhost:8000/health

# Full health check (all services)
curl http://localhost:8000/health/full

# Dashboard metrics
curl http://localhost:8000/metrics
```

---

## Incident Response

### 1. Service Unhealthy

**Symptoms**: `/health/full` shows unhealthy services

**Diagnosis**:
```bash
# Check which service is down
curl http://localhost:8000/health/full | jq '.checks[] | select(.healthy==false)'
```

**Resolution by Service**:

| Service | Resolution |
|---------|------------|
| database | Check DATABASE_URL, restart Postgres |
| r2_storage | Verify R2 credentials, check Cloudflare status |
| huggingface | Check HF_TOKEN, verify quota at huggingface.co |
| gemini | Verify GEMINI_API_KEY, check Google AI status |
| inngest | Restart with `docker-compose restart inngest` |

### 2. Rate Limit Hit (Grok)

**Symptoms**: Jobs stuck at "animate-scenes" step

**Diagnosis**:
```bash
# Check Inngest dashboard for rate limit events
# http://localhost:8288 -> Functions -> video-generation

# Or check API logs
docker-compose logs api | grep "rate limit"
```

**Resolution**:
- Wait 2 hours for automatic recovery (Inngest handles this)
- Or manually resume after rate limit expires:
```bash
# Get video ID from Inngest dashboard
# Trigger manual recovery
curl -X POST http://localhost:8000/jobs/{video_id}/retry
```

### 3. Storage Full (R2)

**Symptoms**: Uploads failing, `/storage/stats` shows >9GB used

**Diagnosis**:
```bash
curl http://localhost:8000/storage/stats
```

**Resolution**:
```bash
# Trigger manual cleanup
curl -X POST http://localhost:8000/storage/cleanup

# Or aggressive cleanup (delete older videos)
curl -X POST "http://localhost:8000/storage/cleanup?days=7"
```

### 4. Job Failed

**Symptoms**: Video status is "FAILED"

**Diagnosis**:
```bash
# Get job details
curl http://localhost:8000/jobs/{video_id}

# Check error in metadata
# Look for "checkpoint" object for partial recovery
```

**Resolution**:
```bash
# Retry from checkpoint (if available)
curl -X POST http://localhost:8000/jobs/{video_id}/retry

# Or restart entire job
curl -X POST http://localhost:8000/jobs/{video_id}/restart
```

---

## Routine Maintenance

### Daily
- [ ] Check `/health/full` all services healthy
- [ ] Review Inngest dashboard for stuck jobs
- [ ] Monitor R2 storage usage (stay under 9GB)

### Weekly
- [ ] Review failed jobs and retry if appropriate
- [ ] Clean up old clips: `POST /storage/cleanup`
- [ ] Check HuggingFace quota remaining

### Monthly
- [ ] Backup completed job metadata
- [ ] Review YouTube upload success rate
- [ ] Update API keys if near expiration

---

## Performance Monitoring

### Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| API Response Time | <500ms | >2000ms |
| Job Success Rate | >95% | <80% |
| R2 Storage | <9GB | >9.5GB |
| HF Quota | >1000s/day | <100s remaining |

### Monitoring Commands

```bash
# Check job metrics
curl http://localhost:8000/metrics | jq '.jobs'

# Check storage metrics  
curl http://localhost:8000/metrics | jq '.storage'

# Check quota metrics
curl http://localhost:8000/metrics | jq '.quota'
```

---

## Backup Procedures

### Export Job Metadata
```bash
# Run from project root
python packages/services/production.py backup
```

This creates JSON backups in `/tmp/video-factory-backups/`

### Database Backup
```bash
# Using pg_dump (replace with your connection string)
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
```

---

## Scaling Considerations

### Current Limits (Free Tier)
- R2 Storage: 10GB
- HuggingFace: GPU seconds per day (varies)
- Grok: ~25-30 generations per 2-hour window

### Scaling Up
1. **More Storage**: Upgrade R2 plan or add aggressive cleanup
2. **More AI**: HuggingFace Pro subscription ($9/mo)
3. **More Grok**: Multiple X/Twitter accounts (not recommended)
4. **More Workers**: Deploy to cloud with Inngest Cloud

---

## Emergency Procedures

### Complete System Reset
```bash
# Stop all services
docker-compose down

# Clear database (DESTRUCTIVE)
cd packages/database && npx prisma migrate reset

# Restart
docker-compose up --build
```

### Force Stop Stuck Jobs
```bash
# Direct database update
curl -X POST http://localhost:8000/jobs/force-stop-all
```

### Rollback Database
```bash
# Restore from backup
psql $DATABASE_URL < backup_YYYYMMDD.sql
```
