# MCP demo: Demo Shop

Demo Shop is broken on purpose. It is a small Next.js shop page with UI and logic bugs, built so you can watch Claude find and fix them through a real browser with MCP, and see how MCP works under the hood. The code is messy, and that is not the point: the point is to get a hang of MCP.

Fixing the bugs is the exercise, so go ahead and fix them, by hand or with Claude. Just don't commit the fixes: the next person needs the shop broken. `git restore mcp/demo-shop` puts the bugs back.

The walkthrough is in [AI Assisted Engineering, Session 3](https://claude.ai/artifact/RJ8dsCQrrkQUBzuwnMJszq#session-3). The [Demo Shop design](https://claude.ai/artifact/KFnTFXZoRS1ejCAvSasL48) shows what the page should look like next to what shipped.

## Run the shop locally

```bash
cd mcp/demo-shop
npm install
npx playwright install chromium
npm run dev
```

Open http://localhost:3000 in Chrome. It looks fine on a laptop. To see it break on a phone:

1. Open DevTools: Cmd+Option+I (Ctrl+Shift+I on Windows).
2. Click inside DevTools, then press Cmd+Shift+M (Ctrl+Shift+M on Windows) to turn on the device toolbar. Without DevTools focused, this shortcut opens Chrome's profile menu instead.
3. Pick an iPhone in the Dimensions menu, or set 375 × 812.

## Run the Playwright tests

```bash
cd mcp/demo-shop
npm test
```

Five tests, no AI involved. They all fail until the bugs are fixed.

## Watch Claude find and fix the bugs with MCP

With the shop running, open a second terminal, start Claude Code from the repo root, and approve the `playwright` and `chrome-devtools` servers when asked:

```bash
claude
```

Start it from the repo root, not `mcp/demo-shop`. From any other folder the servers fail with `CONNECTION_CLOSED` and nothing reaches the log.

In a third terminal, from the repo root, watch every MCP message as it happens:

```bash
tail -F mcp/mcp-wire.log
```

Then ask Claude:

```text
Open http://localhost:3000 at phone size, 375 by 812. List everything that is broken, with a screenshot of each problem.
```

Then ask Claude to fix them:

```text
Fix everything you found. Then check the page again at 375 by 812 and run npm test.
```

When you are done, put the bugs back for the next person, from the repo root:

```bash
git restore mcp/demo-shop
```
