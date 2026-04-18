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
  
  // Navigate to X login with shorter timeout
  console.log('Navigating to X login...');
  try {
    await page.goto('https://x.com/login', { 
      waitUntil: 'domcontentloaded',
      timeout: 30000 
    });
  } catch (e) {
    console.log('Navigation timeout, continuing...');
  }
  
  await page.waitForTimeout(5000);
  await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/01_login_start.png', fullPage: true });
  console.log('Screenshot saved: 01_login_start.png');
  console.log('Current URL:', page.url());
  console.log('Page title:', await page.title());
  
  // Try to find and fill email
  console.log('Looking for email input...');
  const inputs = await page.locator('input').all();
  console.log(`Found ${inputs.length} input fields`);
  
  for (let i = 0; i < inputs.length; i++) {
    const type = await inputs[i].getAttribute('type').catch(() => 'unknown');
    const name = await inputs[i].getAttribute('name').catch(() => 'unknown');
    const autocomplete = await inputs[i].getAttribute('autocomplete').catch(() => 'unknown');
    console.log(`Input ${i}: type=${type}, name=${name}, autocomplete=${autocomplete}`);
  }
  
  // Try to find email/username field
  const emailInput = page.locator('input').filter({ hasAttribute: 'name', hasValue: 'text' }).first();
  const phoneInput = page.locator('input').filter({ hasAttribute: 'name', hasValue: 'phone_number' }).first();
  
  if (await emailInput.count() > 0) {
    console.log('Found text input (email/username)');
    await emailInput.fill('Devinbrumbelow5@gmail.com');
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/02_email_filled.png' });
    
    // Find and click next
    const buttons = await page.locator('button').all();
    console.log(`Found ${buttons.length} buttons`);
    
    for (const btn of buttons) {
      const text = await btn.textContent().catch(() => '');
      if (text.toLowerCase().includes('next') || text.toLowerCase().includes('log')) {
        console.log('Clicking button:', text);
        await btn.click();
        break;
      }
    }
    
    await page.waitForTimeout(3000);
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/03_after_next.png', fullPage: true });
    
    // Look for password
    const passwordInput = page.locator('input[type="password"]').first();
    if (await passwordInput.count() > 0) {
      console.log('Found password field');
      await passwordInput.fill('DeViN156021');
      await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/04_password_filled.png' });
      
      // Find login button
      const loginBtns = await page.locator('button').all();
      for (const btn of loginBtns) {
        const text = await btn.textContent().catch(() => '');
        if (text.toLowerCase().includes('log in') || text.toLowerCase().includes('sign in')) {
          console.log('Clicking login button:', text);
          await btn.click();
          break;
        }
      }
      
      await page.waitForTimeout(5000);
      await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/05_after_login.png', fullPage: true });
      console.log('URL after login:', page.url());
      
      // Check for 2FA
      const content = await page.content();
      if (content.includes('code') || content.includes('verification') || content.includes('Enter')) {
        console.log('⚠️  May need 2FA. Check screenshot 05_after_login.png');
      }
    }
  }
  
  // Try to navigate to Grok
  console.log('Attempting to navigate to Grok...');
  await page.goto('https://x.com/i/grok', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(5000);
  await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/06_grok_page.png', fullPage: true });
  
  console.log('Grok page URL:', page.url());
  console.log('Grok page title:', await page.title());
  
  // Check for chat
  const textareas = await page.locator('textarea, [contenteditable]').all();
  console.log(`Found ${textareas.length} text input areas`);
  
  await browser.close();
  console.log('Session complete.');
})();
