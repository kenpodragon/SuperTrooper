# Application Tracking

How to log applications, update statuses, follow up, and monitor your pipeline.

---

## Concepts

**Application** -- A record of a job you've applied to, with company, role, status, dates, and notes.

**Pipeline** -- Your applications organized by status: Applied, Phone Screen, Interview, Offer, Rejected, Ghosted, Withdrawn.

**Follow-up** -- A logged outreach attempt on an existing application (email, LinkedIn message, phone call).

**Aging** -- Applications that haven't had a status change in a configured number of days. Stale applications need attention.

---

## Workflow 1: Log a New Application

### Quick log

> "I applied to Acme Corp for VP Engineering today"

Claude calls `add_application` with the company name, role, and today's date.

### Detailed log

> "Log an application: Acme Corp, VP Engineering, applied via LinkedIn, JD URL is https://..., notes: referral from Jane Smith"

You can include source (Indeed, LinkedIn, Direct, Recruiter, Referral), JD URL, JD text, and notes.

### From a saved job

If you saved the job first:

> "Convert saved job 12 to an application"

This preserves all the JD text and gap analysis data.

---

## Workflow 2: Update Application Status

### Move through the pipeline

> "Update application 14 to Phone Screen"
> "Application 14 is now at Interview stage"
> "Mark application 14 as Offer"

### Add notes

> "Add notes to application 14: Second round scheduled for March 25"

### Common status values

| Status | Meaning |
|--------|---------|
| Applied | Submitted, waiting to hear back |
| Phone Screen | Initial phone/video screening |
| Interview | In active interview process |
| Offer | Received an offer |
| Accepted | Accepted an offer |
| Rejected | Received a rejection |
| Ghosted | No response after extended time |
| Withdrawn | You withdrew your application |

---

## Workflow 3: Search and Filter Applications

### By status

> "Show all my active applications"
> "Which applications are in Interview status?"

### By company

> "What applications do I have at Google?"

### By source

> "Show me applications from LinkedIn"

### All applications

> "Show all my applications"

---

## Workflow 4: Follow-Ups

### Log a follow-up

> "I sent a follow-up email to Acme Corp about application 14"

Claude calls `log_follow_up` with the application ID, method, and notes.

### Check what needs follow-up

> "Which applications haven't had any activity in 2 weeks?"

Calls `get_stale_applications(days=14)` and returns applications sorted by staleness.

> "Show me applications that need follow-up"

---

## Workflow 5: Pipeline Analytics

### Funnel view

> "Show me my application pipeline stats"

Calls `get_analytics` and returns:
- **Funnel** -- how many applications at each stage
- **Source effectiveness** -- which sources produce the most interviews
- **Monthly activity** -- application volume over time
- **Summary** -- total counts and conversion rates

### Weekly digest

> "Give me a weekly digest"

Summarizes the past week's activity: new applications, status changes, follow-ups, and items needing attention.

### Campaign summary

> "How is my job search campaign going overall?"

Returns high-level campaign metrics.

---

## Workflow 6: Aging and Link Monitoring

### Check for stale applications

> "What's going stale in my pipeline?"

Returns the aging summary across all statuses.

### Check if a job posting is still active

> "Check if the posting for application 14 is still live"

Calls `check_posting_status` to verify the job URL is still active.

### Get the full aging summary

> "Give me an aging summary"

Shows application counts by age bucket (1 week, 2 weeks, 1 month, etc.).

---

## Workflow 7: Email Intelligence

### Scan emails for status updates

> "Scan my emails for application status changes"

Calls `scan_emails_for_status` which looks for signals like rejection emails, interview invitations, and offer letters in your email history.

### Detect ghosted applications

> "Which applications might be ghosted?"

Uses email intelligence to identify applications with no response after a configurable threshold.

---

## Tips

- Always include JD text when logging applications... it enables gap analysis and skill tracking
- Link applications to companies in your target list for richer dossier data
- Log every follow-up to maintain an accurate timeline
- Review the aging summary weekly to catch applications going stale
- Use the pipeline analytics to understand which sources and approaches work best
