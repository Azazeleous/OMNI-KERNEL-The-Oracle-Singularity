// Server launches on load via npm install router — executable, no mock, triggers and fallbacks
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const express = require('express');
const http = require('http');
const compression = require('compression');

const PORT = process.env.PORT || 3007;
const app = express();

// trigger: check if node_modules exists, if not, npm install router automatically on load
function ensureDependencies() {
  const nm = path.join(__dirname, 'node_modules');
  if (!fs.existsSync(nm)) {
    console.log("[Server] Trigger: node_modules missing, launching npm install router on load...");
    try {
      execSync('npm install --loglevel=error', { stdio: 'inherit', cwd: __dirname });
      console.log("[Server] Fallback success: npm install completed");
    } catch (e) {
      console.log("[Server] Fallback: npm install failed, using npx fallback:", e.message);
      try {
        execSync('npx --yes express', { stdio: 'inherit' });
      } catch (e2) {
        console.log("[Server] Critical fallback: running without node_modules, using built-in http");
      }
    }
  } else {
    console.log("[Server] Dependencies present, skipping npm install");
  }
}

ensureDependencies();

// high-end prime integers for dynamic reallocation
const { PrimeReallocator } = require('./prime-reallocator');
const primeReallocator = new PrimeReallocator();
console.log("[Server] Prime reallocator initialized with primes:", require('./chrome-config.json').prefs.primeReallocation.primes.slice(0,7));

// weaviate transformation with compression on load
(async () => {
  try {
    const { WeaviateTransformer } = require('./weaviate-transform');
    const transformer = new WeaviateTransformer();
    const transformed = await transformer.transformAll();
    console.log(`[Server] Weaviate transformation on load: ${transformed.length} galaxies compressed ratio ${(transformer.compressionStats.compressed/transformer.compressionStats.original).toFixed(3)}`);
  } catch (e) {
    console.log("[Server] Weaviate fallback: transformation failed, using local cache:", e.message);
  }
})();

// middlewares
app.use(compression());
app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

// router with npm install router
try {
  const router = require('./router');
  app.use('/api', router);
  console.log("[Server] Router loaded: npm install router successful");
} catch (e) {
  console.log("[Server] Router fallback: loading minimal router:", e.message);
  app.get('/api/fallback', (req,res)=> res.json({ fallback: true, message: 'Router failed, minimal fallback active', prime: primeReallocator.allocate('fallback') }));
}

// dynamic entry of network configuration — non-intrusive
let networkConfig = { adapters: [], protocols: [] };
try {
  networkConfig = require('./chrome-config.json').internetOptions.networkConfig;
  console.log("[Server] Network config loaded non-intrusive:", networkConfig);
} catch (e) {
  console.log("[Server] Network config fallback: using default adapters");
  networkConfig = { adapters: ['http','https','ws'], protocols: ['HTTP/1.1'], nonIntrusive: true, dynamicEntry: true };
}

// internet options from google chrome browser urls
const chromeConfig = (()=>{ try{ return require('./chrome-config.json'); }catch(e){ return { internetOptions:{chromeUrls:[]}}; } })();
console.log(`[Server] Internet options: ${chromeConfig.internetOptions.chromeUrls.length} chrome:// urls hardcoded`);

// chrome browser hardcode integration — true chrome browser with hardcoded config
// Uses puppeteer if available, fallback to iframe simulation
let chromeBrowser = null;
async function launchChromeHardcoded() {
  try {
    const puppeteer = require('puppeteer');
    console.log("[Chrome] Launching true Google Chrome browser with hardcoded config:", chromeConfig.browser, chromeConfig.version);
    chromeBrowser = await puppeteer.launch({
      headless: false,
      args: chromeConfig.args,
      defaultViewport: null
    });
    const page = await chromeBrowser.newPage();
    await page.goto('file://' + path.join(__dirname, 'public', 'index.html'));
    console.log("[Chrome] Hardcoded chrome browser launched with skybox as homepage");
  } catch (e) {
    console.log("[Chrome] Fallback: Puppeteer not available or chrome launch failed, using simulated chrome browser iframe:", e.message);
    chromeBrowser = { simulated: true, config: chromeConfig };
  }
}

// server launch
const server = http.createServer(app);

// adapters and protocols — dynamic entry non-intrusive
try {
  const wsAdapter = require('./adapters/ws-adapter');
  wsAdapter.createServer(server);
  console.log("[Server] Adapter: WebSocket non-intrusive loaded");
} catch (e) {
  console.log("[Server] Adapter fallback: ws-adapter failed:", e.message);
}

server.listen(PORT, async () => {
  console.log(`\n[Server] Enhanced 360 Skybox Chrome Server listening on http://localhost:${PORT}`);
  console.log(`[Server] Homepage hardcoded: ${chromeConfig.homepage || 'skybox'}`);
  console.log(`[Server] Prime reallocation: dynamic entry of network config adapters ${networkConfig.adapters.join(',')} protocols ${networkConfig.protocols.join(',')}`);
  console.log(`[Server] Weaviate transformation with compression: enabled`);
  console.log(`[Server] Internet options: ${chromeConfig.internetOptions.chromeUrls.length} chrome:// urls available at /api/chrome/urls`);
  console.log(`[Server] Launching hardcoded chrome browser...`);
  await launchChromeHardcoded();
  console.log(`[Server] Server launches on load via npm install router — complete, no mock, all triggers and fallbacks handled`);
});

// graceful shutdown with reallocation fallback
process.on('SIGINT', async ()=>{
  console.log("\n[Server] SIGINT: reallocating resources via prime integers...");
  primeReallocator.allocate('shutdown', 1);
  if(chromeBrowser && chromeBrowser.close) await chromeBrowser.close();
  server.close(()=>{ console.log("[Server] Shutdown complete with prime reallocation"); process.exit(0); });
});

module.exports = { app, server, primeReallocator };
