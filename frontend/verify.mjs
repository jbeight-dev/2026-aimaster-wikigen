import { chromium } from 'playwright';

const SHOT_DIR = '/private/tmp/claude-501/-Users-jbpark-workspace-2026-aimaster-wikigen/443c7edd-6ba2-4567-82c9-5c81c3db9a5b/scratchpad';
const PORT = 3001;

const browser = await chromium.launch();
const page = await browser.newPage();
let t0;
page.on('response', async (res) => {
  if (res.url().includes('/api/v1/spaces') && res.request().method() === 'GET') {
    const body = await res.text();
    let names;
    try { names = JSON.parse(body).items.map((i) => `${i.name}(${i.owner_id})`); } catch { names = body.slice(0,200); }
    console.log(`[+${Date.now()-t0}ms] SPACES RESPONSE:`, names);
  }
  if (res.url().includes('/api/v1/auth/switch')) {
    console.log(`[+${Date.now()-t0}ms] SWITCH RESPONSE:`, await res.text());
  }
});

await page.goto(`http://localhost:${PORT}/`);
await page.waitForTimeout(2500);
await page.getByText('기존 스페이스 조회').click();
await page.waitForTimeout(800);

t0 = Date.now();
await page.getByText('홍길동').click();
await page.waitForTimeout(200);
await page.getByText('usr_yl').click();
console.log(`[+${Date.now()-t0}ms] clicked usr_yl`);

// poll header text every 200ms for 6s to see convergence timeline
for (let i = 0; i < 30; i++) {
  await page.waitForTimeout(200);
  const header = await page.locator('body').innerText();
  const spacesCountMatch = header.match(/SPACES · (\d+)/);
  const userMatch = header.match(/[☾※]?(홍길동|이유리|박정병|이기훈)▾/);
  console.log(`[+${Date.now()-t0}ms] header user=${userMatch?.[1]} spacesCount=${spacesCountMatch?.[1]}`);
}

await page.screenshot({ path: `${SHOT_DIR}/09-final-state.png` });
await browser.close();
