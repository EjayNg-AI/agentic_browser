# Agent Protocol

- Use only the `/v1/run_steps` endpoint with the allowed step types: `goto`, `click`, `type`, `press`, `wait_for`, `scroll`, `extract`, `extract_readable`, `links`, `quote`, `screenshot`, `pause_for_user`.
- Keep extracted text small and focused; include the source URL in notes and outputs.
- Stop and request Manual Assist whenever blocked (CAPTCHA, login/MFA, bot interstitials, paywalls, consent walls).
