# Production Deployment Checklist

## Pre-Deployment Phase

### 1. Code Review & Quality ✓
- [x] All features implemented (Features 1-13)
- [x] Code review completed for all features
- [x] CRITICAL issues resolved (asyncio import, recursion protection)
- [x] Code quality tools configured (Black, isort, flake8, mypy, pylint, bandit)
- [x] Pre-commit hooks active
- [x] All tests passing (100+ test cases)

### 2. Environment Configuration
- [ ] Production `.env` file created
- [ ] All API keys rotated for production
- [ ] Database connection string configured (Neon or self-hosted)
- [ ] Redis connection string configured (Upstash or Redis Cloud)
- [ ] Twilio credentials verified
- [ ] Deepgram API key verified
- [ ] OpenAI API key verified
- [ ] Google Calendar OAuth2 credentials configured
- [ ] `BASE_URL` set to production domain
- [ ] `ENV=production` set
- [ ] `DEBUG=false` set
- [ ] **CRITICAL:** `YOUR_TEST_NUMBER` removed or commented out

### 3. Database Setup
- [ ] Production database created
- [ ] Database user with appropriate permissions created
- [ ] Connection pooling configured (pool_size=20, max_overflow=40)
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Database indexes verified
- [ ] Performance tuning applied (shared_buffers, effective_cache_size)
- [ ] Backup schedule configured
- [ ] Test backup restoration

### 4. Redis Setup
- [ ] Production Redis instance created
- [ ] Redis password configured
- [ ] Connection pooling configured
- [ ] Memory limits set (maxmemory 512mb)
- [ ] Eviction policy set (allkeys-lru)
- [ ] Persistence configured (if needed)
- [ ] Test Redis connection

### 5. Domain & SSL
- [ ] Domain name registered
- [ ] DNS A record pointing to server IP
- [ ] SSL/TLS certificate obtained (Let's Encrypt)
- [ ] Certificate auto-renewal configured
- [ ] HTTPS redirect configured
- [ ] Test SSL configuration (https://www.ssllabs.com/ssltest/)

### 6. Twilio Configuration
- [ ] Twilio phone number purchased
- [ ] Media Streams enabled on phone number
- [ ] Webhook URLs updated to production domain:
  - Inbound call: `https://yourdomain.com/api/v1/webhooks/inbound-call`
  - Outbound reminder: `https://yourdomain.com/api/v1/webhooks/outbound-reminder`
- [ ] Test call completed successfully
- [ ] Verify WebSocket connection working
- [ ] Check audio quality

---

## Deployment Phase

### 7. Server Deployment
- [ ] Server deployed (Railway/Docker/Systemd)
- [ ] Nginx reverse proxy configured
- [ ] WebSocket support verified in Nginx config
- [ ] Worker processes configured (--workers 4)
- [ ] Health check endpoint responding (`/health`)
- [ ] CORS configuration verified
- [ ] Rate limiting configured (if applicable)
- [ ] Server logging to file/stdout

### 8. Worker Deployment
- [ ] Worker deployed (Docker/Systemd)
- [ ] APScheduler cron job configured
- [ ] Timezone configured correctly (WORKER_REMINDER_TIMEZONE)
- [ ] Reminder hour configured (WORKER_REMINDER_HOUR)
- [ ] Test reminder job manually
- [ ] Verify worker connects to database
- [ ] Verify worker connects to Redis
- [ ] Worker logging configured

### 9. Monitoring & Alerting
- [ ] Uptime monitoring configured (UptimeRobot/Pingdom)
- [ ] Error tracking configured (Sentry)
- [ ] Log aggregation configured (Better Stack/Logtail)
- [ ] Metrics dashboard created
- [ ] Alerts configured for:
  - Server down
  - High error rate (>5%)
  - High latency (>2s)
  - Database connection failures
  - Redis connection failures
  - Worker job failures
- [ ] On-call rotation defined
- [ ] Incident response plan documented

### 10. Performance Validation
- [ ] Customer lookup latency validated (<2ms cached, <30ms uncached)
- [ ] STT→LLM latency validated (<800ms)
- [ ] LLM→TTS latency validated (<500ms)
- [ ] Barge-in response validated (<200ms)
- [ ] End-to-end latency validated (<2s)
- [ ] Concurrent call capacity tested (target: 10-20 concurrent)
- [ ] Database query performance validated
- [ ] Redis response time validated

---

## Security Phase

### 11. Security Hardening
- [ ] `.env` file permissions set to 600
- [ ] Database credentials rotated
- [ ] Redis password set and secured
- [ ] API keys secured (never in code/logs)
- [ ] Rate limiting enabled on webhooks
- [ ] Input validation tested (phone, email, VIN, state codes)
- [ ] SQL injection tests passed
- [ ] XSS prevention verified
- [ ] HTTPS enforced (HTTP redirects to HTTPS)
- [ ] Security headers configured:
  - X-Frame-Options: DENY
  - X-Content-Type-Options: nosniff
  - X-XSS-Protection: 1; mode=block
  - Strict-Transport-Security

### 12. Data Protection
- [ ] PII handling documented
- [ ] Sensitive data masked in logs
- [ ] Data retention policy defined
- [ ] GDPR compliance reviewed (if applicable)
- [ ] Customer data isolation tested
- [ ] Backup encryption configured
- [ ] Access control documented

### 13. Compliance & Legal
- [ ] Terms of Service reviewed
- [ ] Privacy Policy reviewed
- [ ] TCPA compliance verified (for outbound calls)
- [ ] Recording consent verified (if recording calls)
- [ ] Data processing agreement with third parties (Twilio, Deepgram, OpenAI)

---

## Testing Phase

### 14. Integration Testing
- [ ] End-to-end test suite run (30+ tests)
- [ ] All CRM tools tested (lookup, book, cancel, reschedule)
- [ ] Conversation flows tested (new customer, existing customer, reschedule, inquiry)
- [ ] Error handling tested (invalid input, timeouts, API failures)
- [ ] Barge-in functionality tested
- [ ] Session management tested
- [ ] Tool call recursion protection tested

### 15. Load Testing
- [ ] 10 concurrent calls tested
- [ ] 50 concurrent customer lookups tested
- [ ] 100 concurrent sessions tested
- [ ] Database connection pool under load tested
- [ ] Redis performance under load tested
- [ ] System recovery after load tested

### 16. User Acceptance Testing
- [ ] Test with real customer scenarios:
  - New customer booking first appointment
  - Existing customer booking second appointment
  - Customer rescheduling appointment
  - Customer canceling appointment
  - Customer asking about services
  - Customer requesting to speak to manager (escalation)
- [ ] Audio quality validated
- [ ] Conversation flow natural
- [ ] AI responses accurate and helpful
- [ ] Tool calls working correctly

---

## Go-Live Phase

### 17. Final Checks
- [ ] All previous checklist items completed
- [ ] Production environment tested end-to-end
- [ ] Rollback plan documented
- [ ] Team trained on monitoring and incident response
- [ ] Support documentation updated
- [ ] Customer-facing documentation updated (if any)

### 18. Launch
- [ ] **Remove POC safety:** Delete or comment `YOUR_TEST_NUMBER` in `.env`
- [ ] Restart all services to pick up production config
- [ ] Verify health check endpoints
- [ ] Monitor error rates for first hour
- [ ] Monitor performance metrics
- [ ] Test with real customer call (staff member)
- [ ] Announce launch to team

### 19. Post-Launch Monitoring (First 24 Hours)
- [ ] Monitor error rates every hour
- [ ] Monitor call success rates
- [ ] Monitor performance metrics
- [ ] Check for any anomalies
- [ ] Review logs for unexpected errors
- [ ] Verify all scheduled jobs running
- [ ] Customer feedback collected

---

## Ongoing Maintenance

### Daily Tasks
- [ ] Review error rates and logs
- [ ] Check system health dashboard
- [ ] Monitor API usage and costs
- [ ] Review customer feedback

### Weekly Tasks
- [ ] Performance metrics review
- [ ] Security patch updates
- [ ] Database vacuum (if self-hosted)
- [ ] Backup verification
- [ ] Cost analysis

### Monthly Tasks
- [ ] Security audit
- [ ] Performance optimization review
- [ ] Dependency updates
- [ ] Backup restoration test
- [ ] Incident review
- [ ] Capacity planning

---

## Rollback Plan

### If Issues Detected Post-Launch

1. **Immediate Actions:**
   - Re-enable `YOUR_TEST_NUMBER` restriction
   - Update Twilio webhook to old system (if replacing existing)
   - Restart services with rollback config

2. **Database Rollback:**
   ```bash
   # Rollback last migration
   alembic downgrade -1
   ```

3. **Code Rollback:**
   ```bash
   git revert HEAD
   git push origin main
   # Redeploy
   ```

4. **Communication:**
   - Notify team of rollback
   - Document issues encountered
   - Create incident report
   - Plan fixes for next deployment

---

## Success Criteria

### Launch is successful if:
- ✅ Zero critical errors in first 24 hours
- ✅ >95% call success rate
- ✅ Average end-to-end latency <2 seconds
- ✅ Zero customer complaints about audio quality
- ✅ All appointments booked correctly
- ✅ All reminder calls sent on schedule
- ✅ No security incidents
- ✅ System uptime >99.9%

---

## Emergency Contacts

**On-Call Engineer:** [Name, Phone]
**Database Admin:** [Name, Phone]
**DevOps Lead:** [Name, Phone]
**Product Owner:** [Name, Phone]

**Third-Party Support:**
- Twilio Support: https://support.twilio.com
- Deepgram Support: https://deepgram.com/contact-us
- OpenAI Support: https://help.openai.com
- Neon Support: https://neon.tech/docs/introduction/support

---

## Notes

**Last Updated:** 2025-01-12
**Deployment Target:** Production
**Expected Launch Date:** [TBD]
**Responsible Team:** [Your Team Name]
