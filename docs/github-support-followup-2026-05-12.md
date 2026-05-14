# GitHub Support Follow-Up Email — Ticket #4360519

> Gönderileceği yer: https://support.github.com/contact/private?ticket=4360519
> Tarih: 2026-05-12

---

## Konu / Subject

```
Follow-up on Ticket #4360519 — Account flag still blocking third-party OAuth (6 days)
```

## Mesaj / Message Body

```
Hi GitHub Support team,

I'm following up on ticket #4360519, opened on 2026-05-06. It has been 6 days
since the initial report, and the account `celikada` is still flagged.

Current symptom (unchanged): When I try to authorize SonarCloud's OAuth app
at https://sonarcloud.io with my GitHub account, the GitHub OAuth
authorization page returns:

  "This account is flagged, and therefore cannot authorize a third party
   application."

Importantly:
- The flag only triggers on third-party OAuth authorization flows.
- All my other GitHub operations work normally: I can commit, push, manage
  branches, manage branch protection rules, use Personal Access Tokens
  (e.g., GHCR push), and view my profile.
- The blocker is specifically the OAuth handshake step required by
  third-party services like SonarCloud, Vercel, etc.

Concrete impact:
- I cannot enable SonarCloud Code Analysis on my open-source project
  https://github.com/celikada/KFinans.
- The Sonar quality gate is a required check for my CI/CD pipeline before
  the first production release (planned for v0.1.0 of the KFinans personal
  finance dashboard).
- This is the only remaining blocker before production launch — all my
  technical hardening (security headers, KVKK compliance, observability,
  test coverage) is complete and waiting on this OAuth gate.

I have not received any further communication on the original ticket. Could
you please:

1. Confirm whether the ticket is still under review or if additional info
   is needed from me.
2. Provide an estimated time for review completion, if known.
3. If there are any actions I can take to expedite the reinstatement
   (e.g., re-verify identity, add 2FA, etc.), I'm happy to do so.

For context: the flag was triggered after a high-volume commit/push window
during initial repository setup (making the repo public, enabling branch
protection, ~8 commits in a short timeframe). I am a legitimate solo
developer of a personal finance application, building it for my own use
under the Mayotek brand. The repository is open-source (Apache-2.0
license) and follows standard open-source contribution patterns.

Thanks for your time and consideration.

Best regards,
[Your name]
GitHub username: celikada
Repository: https://github.com/celikada/KFinans
Original ticket: #4360519
```

---

## Notlar

- Ticket sayfasından "Reply" / "Add to conversation" ile gönder, yeni ticket açma.
- 6 günden uzun süre yanıt yoksa Twitter (`@GitHubSupport`) ile public takip
  yapılabilir — ama özel veri içermediği için sadece "Hi, can someone check
  ticket #4360519? It's been 6 days." gibi kısa bir mesaj yeterli.
- Production hazırlığı (KFinans v0.1.0) bu ticket'in çözümüne bağlı —
  workflow `continue-on-error: true` ile bypass var ama Sonar quality gate
  zorunlu hale getirilemiyor.
- Bekleme süresinde alternatif: SonarQube Community (self-hosted Oracle VM
  Docker container) — ama setup overhead var, ileride yapılabilir.

## Bekleme süresi referansı

- GitHub Support resmi: "high volume" → 24-48 saat (initial)
- Reinstatement ticket gerçek: tipik 3-14 gün, bazen daha uzun
- Mayıs/Haziran (post-Copilot launch dönemi) flag volume yüksek → daha uzun
