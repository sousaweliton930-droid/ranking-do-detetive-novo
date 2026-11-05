// Execute com Playwright e Chromium instalados; usa somente a prévia local vazia.
const { chromium } = require('playwright');
const base=process.env.PREVIEW_URL || 'http://127.0.0.1:8000';
(async () => {
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',args:['--no-sandbox']});
  for (const width of [390,1440]) {
    const page=await browser.newPage({viewport:{width,height:1000}});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    for(const path of ['/','/atualizacao','/carteira','/canais','/admin/login']) {
      const response=await page.goto(base+path);
      if(response.status()!==200) throw Error(path+' status '+response.status());
      if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw Error('Overflow '+width+' '+path);
      await page.locator('h1').waitFor();
    }
    await page.goto(base);
    await page.getByRole('link',{name:'Carteira pública'}).click();
    await page.getByText('Nenhuma entrada neste período').waitFor();
    if(errors.length) throw Error(errors.join('\n'));
    await page.close(); console.log('Browser OK: '+width+'px');
  }
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
