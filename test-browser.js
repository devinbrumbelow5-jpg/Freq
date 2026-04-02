const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.goto('https://example.com');
  const title = await page.title();
  console.log('Page title:', title);
  
  await page.screenshot({ path: '/root/.openclaw/workspace/test-screenshot.png' });
  console.log('Screenshot saved to test-screenshot.png');
  
  await browser.close();
})();
