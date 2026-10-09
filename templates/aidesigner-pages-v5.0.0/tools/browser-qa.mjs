import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import { createServer } from 'node:http';
import { readFile, stat, mkdir, writeFile } from 'node:fs/promises';
import { resolve, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const dist = resolve(root, 'dist');
const mime = { '.html':'text/html', '.css':'text/css', '.js':'text/javascript', '.svg':'image/svg+xml' };
const server = createServer(async (req,res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url,'http://qa.invalid').pathname);
    // A project subpath is deliberate: root-only links must fail this check.
    if (!pathname.startsWith('/project/')) { res.writeHead(404).end(); return; }
    const file = resolve(dist, '.' + pathname.slice('/project'.length));
    if (relative(dist,file).startsWith('..')) { res.writeHead(403).end(); return; }
    const candidate = (await stat(file)).isDirectory() ? resolve(file,'index.html') : file;
    res.writeHead(200,{'Content-Type':mime[extname(candidate)] || 'application/octet-stream'});
    res.end(await readFile(candidate));
  } catch { res.writeHead(404).end(); }
});
await new Promise(r => server.listen(0,'127.0.0.1',r));
const url = `http://127.0.0.1:${server.address().port}/project/`;
const results = [], failures = [];
let browser;
try {
  browser = await chromium.launch({headless:true});
  for (const width of [320,390,768,1440]) {
    const context = await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
    const page = await context.newPage();
    page.on('pageerror',error => failures.push({width,rule:'JavaScript runtime error',message:error.message}));
    page.on('response',response => { if (response.status() >= 400) failures.push({width,rule:'Resource failed',status:response.status()}); });
    page.on('request',request => { if (!request.url().startsWith(url)) failures.push({width,rule:'Unexpected network request'}); });
    await page.goto(url,{waitUntil:'load'});
    const measure = await page.evaluate(() => ({overflow:document.documentElement.scrollWidth>window.innerWidth+1,h1:document.querySelectorAll('h1').length}));
    if (measure.overflow) failures.push({width,rule:'Horizontal overflow'});
    if (measure.h1 !== 1) failures.push({width,rule:'Missing primary heading'});
    const accessibility = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
    for (const violation of accessibility.violations) failures.push({width,rule:violation.id,impact:violation.impact,elements:violation.nodes.length});
    await page.keyboard.press('Tab');
    const firstFocus = await page.evaluate(() => document.activeElement?.textContent?.trim());
    if (firstFocus !== 'Skip to content') failures.push({width,rule:'Skip link is not first keyboard target'});
    await page.keyboard.press('Enter');
    const focused = await page.evaluate(() => document.activeElement?.id);
    // Some browsers focus the main element only when tabindex=-1 is supplied.
    if (focused !== 'main') failures.push({width,rule:'Skip link does not focus main'});
    await page.getByRole('link',{name:'Use the workflow',exact:true}).click();
    if (!page.url().endsWith('#workflow')) failures.push({width,rule:'Primary CTA destination failed'});
    await page.getByText('How does this connect to AIDesigner?',{exact:true}).click();
    if (!await page.getByText('Read AIDesigner\'s documentation',{exact:true}).isVisible()) failures.push({width,rule:'FAQ does not expand'});
    await context.grantPermissions(['clipboard-write','clipboard-read']);
    await page.getByRole('button',{name:'Copy the brief',exact:true}).click();
    if (!(await page.locator('#copy-status').innerText()).startsWith('Brief copied.')) failures.push({width,rule:'Clipboard action failed'});
    const clipboard = await page.evaluate(() => navigator.clipboard.readText());
    if (!clipboard.startsWith('Design a landing page')) failures.push({width,rule:'Clipboard did not contain the brief'});
    await page.goto(url,{waitUntil:'load'});
    await mkdir(resolve(root,'.evidence'),{recursive:true});
    await page.screenshot({path:resolve(root,`.evidence/viewport-${width}.png`),fullPage:true});
    results.push({width,accessibility_violations:accessibility.violations.length,overflow:measure.overflow});
    await context.close();
  }
} catch (error) { failures.push({rule:'QA could not complete',message:error.message}); }
finally { if (browser) await browser.close(); await new Promise(r=>server.close(r)); }
const report = {time:new Date().toISOString(),gate:'REVERIFY',passed:failures.length===0,viewports:results,failures,scope:'headless Chromium with axe; manual review and other browser engines remain separate'};
await mkdir(resolve(root,'.evidence'),{recursive:true});
await writeFile(resolve(root,'.evidence/browser.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
process.exitCode = report.passed ? 0 : 1;
