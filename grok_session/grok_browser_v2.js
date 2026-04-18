const { chromium } = require('playwright');

(async () => {
  console.log('Launching browser...');
  const browser = await chromium.launch({ 
    headless: true
  });
  
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  
  const page = await context.newPage();
  
  // Try different Grok URLs
  const urls = [
    'https://x.ai/grok',
    'https://grok.x.ai',
    'https://twitter.com/i/grok',
    'https://x.com/i/grok'
  ];
  
  for (const url of urls) {
    console.log(`\nTrying: ${url}`);
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(5000);
      
      const currentUrl = page.url();
      const title = await page.title();
      console.log(`  URL: ${currentUrl}`);
      console.log(`  Title: ${title}`);
      
      // Check for Cloudflare
      const content = await page.content();
      if (content.includes('cloudflare') || content.includes('Attention Required')) {
        console.log('  ⚠️  Blocked by Cloudflare');
        continue;
      }
      
      // Check for login
      const hasLogin = await page.locator('input[type="email"], input[type="text"], input[type="password"], text=Sign in').count() > 0;
      const hasChat = await page.locator('textarea, [contenteditable="true"]').count() > 0;
      
      console.log(`  Has login elements: ${hasLogin}`);
      console.log(`  Has chat elements: ${hasChat}`);
      
      await page.screenshot({ path: `/root/.openclaw/workspace/grok_session/screenshot_${url.replace(/[^a-z]/g, '_')}.png`, fullPage: true });
      
      if (hasChat) {
        console.log('  ✅ Chat interface found!');
        break;
      }
    } catch (e) {
      console.log(`  Error: ${e.message}`);
    }
  }
  
  // Final screenshot of whatever page we're on
  await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/final_page.png', fullPage: true });
  console.log('\nFinal page saved to final_page.png');
  
  await browser.close();
  console.log('Browser session complete.');
})();
