# Hackathon Submission Checklist

**Owner:** Lane D. Tick items only when they are truly done. Add a name and date next to each.

## Required deliverables

| # | Deliverable | Done | Owner / date | Notes |
|---|---|---|---|---|
| 1 | Problem statement and solution summary | [ ] | | Source: `README.md` (Problem, Solution) |
| 2 | Readable, executable source code as a ZIP | [ ] | | See packaging below |
| 3 | Five-minute solution video | [ ] | | Script: `docs/demo-script.md` |
| 4 | Bob prompts and examples of usage | [ ] | | `prompts/example-prompts.md`, plus real output from a Bob session |
| 5 | Team member feedback on Bob | [ ] | | `docs/bob-feedback.md`, written by each teammate |

## Definition of done (from `Team_Lanes.md`, section 8)

- [ ] SalesFlow mode appears in Bob IDE and can be selected.
- [ ] MCP server starts from documented steps.
- [ ] At least two actual MCP calls are observable in a live Bob conversation.
- [ ] Acme account and opportunity data are correctly retrieved.
- [ ] 6 to 10 SPIN discovery questions are relevant to the synthetic opportunity.
- [ ] Brief distinguishes sourced facts, assumptions, and unknowns.
- [ ] Product claims are grounded. No invented pricing or unsupported competitive comparison.
- [ ] No external emails sent. No real data used. No unauthorized data writes.
- [ ] README includes verified run and test instructions, and the demo is recorded.
- [ ] All contributors provide their own honest Bob feedback.

## Pre-submission checks

- [ ] `README.md` "Current status" table matches reality.
- [ ] `data/playbooks/*.json` exists, or the README and demo script state that playbooks are not included.
- [ ] `.bob/mcp.json` contains no personal absolute paths and no secrets.
- [ ] No `.env`, credentials, `.venv`, or `outputs/` content in the ZIP or the repository.
- [ ] All data and screenshots are synthetic.
- [ ] A teammate other than the author ran the setup from a clean clone and it worked. Name: ________
- [ ] Every claim in the video is true of the code in the ZIP.
- [ ] Demo rehearsed at least three times and under five minutes (log in `docs/demo-script.md`).

## Packaging the ZIP

Use the git history so ignored files are excluded:

```bash
cd <repo>
git switch main && git pull
git archive --format=zip --output=../SalesFlow-submission.zip HEAD
unzip -l ../SalesFlow-submission.zip | head -50     # inspect the contents
```

`git archive` includes only tracked files, so `.venv/`, `.env`, and `outputs/` content are left out. Confirm that `mcp-server/uv.lock` is included.

## Video checklist

- [ ] Under five minutes.
- [ ] Shows mode selection, the MCP server connected, and at least two live tool calls.
- [ ] Shows grouped SPIN questions, Verified, Assumed, and Unknown tags, and a guardrail refusal.
- [ ] Says clearly that the data is synthetic and that nothing is sent.
- [ ] If any part is recorded or replayed instead of live, it is labelled.

## Open questions for the leads

1. Which lane will deliver `data/playbooks/*.json`, and by when?
2. Does the relative `uv --directory mcp-server` form work in Bob, or should the README tell teammates to use their global MCP file?
3. The Word export (PR #3) now writes to `outputs/`. Should the demo show it? It needs one successful run in Bob first.
4. Who approves the proposed PRD and README changes in `docs/prd-revisions.md`?
5. Who owns catalog verification (PRD revision R-11)?
