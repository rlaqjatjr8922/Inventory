// Run with Node and Playwright available in NODE_PATH. All requests use fixtures.
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
(async () => {
 const browser = await chromium.launch({headless:true, channel: process.env.PLAYWRIGHT_CHANNEL || "msedge"});
 try {
 const page = await browser.newPage({viewport:{width:1280,height:1000}});
 const errors = []; page.on('pageerror', e => errors.push(e.message));
 let item = {'메모키':'1','버전':'v1','상위태그':'글카','제목':'GTX 960 수리','우선도':2,'상태':'진행중','최종결론':'저장된 결론','작업내용':[
  {'작업날짜':'2026-09-20','요약':'무출력 증상 확인','세부':'글카수리시작\n{12:[1,2,999]}\n사진에 보이는 두 지점\n{13:[1,3,4]}\n다음 설명\n{12:1}\n{999:1}\n마지막 <script>alert(1)</script>'},
  {'작업날짜':'2026-09-21','요약':'전원부 전압 측정','세부':'두 번째 작업'}]};
 let revision=1; const writes=[]; let latest={image_id:null,revision:0};
 // A PNG created in browser gives a real intrinsic image box for overlay checks.
 await page.goto('about:blank');
 const png = await page.evaluate(() => {const c=document.createElement('canvas'); c.width=1000;c.height=500;const x=c.getContext('2d');x.fillStyle='#dbeafe';x.fillRect(0,0,1000,500);return c.toDataURL().split(',')[1];});
 await page.route('http://inventory.test/**', async route => {
  const req=route.request(), url=new URL(req.url()), pathname=url.pathname;
  const json = body => route.fulfill({json:body});
  if(pathname==='/') {
   let html=fs.readFileSync(path.join(root,'wap/main.htm'),'utf8').replace(/<script src="\/js\/(?!memory\.js)[^"]+"><\/script>/g,'');
   return route.fulfill({contentType:'text/html',body:html});
  }
  if(pathname.startsWith('/css/') || pathname.startsWith('/js/')) return route.fulfill({path:path.join(root,'wap',pathname)});
  if(pathname==='/api/memory/latest-image') return json(latest);
  if(pathname==='/api/memory/categories') return json(['글카','기타']);
  if(pathname==='/api/memories' && req.method()==='GET') return json([item]);
  if(pathname.startsWith('/api/images/')) {
   const id=Number(pathname.split('/').pop());
   if(id===999) return route.fulfill({status:404,json:{detail:'missing'}});
   return json({image_id:id,content_items:[{type:'image',mimeType:'image/png',data:png}],points:[1,2,3,4].map(n=>({image_id:id,point_id:n,x:n/5,y:n/5,annotation:`주석 ${n}`}))});
  }
  if(req.method()!=='GET') {
   const body=req.postDataJSON(); writes.push({method:req.method(),pathname,body});
   if(pathname.includes('/works/')) {const i=Number(pathname.split('/').pop());if(req.method()==='DELETE')item['작업내용'].splice(i,1);else item['작업내용'][i]={'작업날짜':body['작업날짜'],'요약':body['요약'],'세부':body['세부']};}
   else if(req.method()==='PATCH') Object.assign(item,body);
   item['버전']=`v${++revision}`; return json(item);
  }
  return route.fulfill({status:404,body:'not found'});
 });
 await page.goto('http://inventory.test/');
 await page.evaluate(()=>{document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));document.querySelector('#page-memory').classList.add('active');});
 await page.waitForSelector('.memory-list-card');
 assert.equal(await page.locator('#memory-saved-sections').isVisible(),false);
 assert.equal(await page.locator('#add-memory-category-button').count(),0);
 assert.equal(await page.locator('#add-memory-work-button').count(),0);
 await page.locator('.memory-list-card').click();
 assert.equal(await page.locator('#memory-editor-title').innerText(),'메모 보기');
 assert.equal(await page.locator('.memory-work-link').count(),2);
 if(process.env.MEMORY_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.MEMORY_SCREENSHOT_DIR,'memo-view.png'),fullPage:true});
 await page.locator('#memory-title').fill('미저장 제목');
 await page.locator('#reset-memory-button').click();
 assert.equal(await page.locator('#memory-title').inputValue(),'GTX 960 수리');
 assert.equal(writes.length,0);
 await page.locator('#memory-title').fill('새 저장 제목');
 await page.locator('#save-memory-button').click();
 await page.waitForFunction(()=>document.querySelector('#memory-message').textContent==='저장했습니다.');
 assert.equal(writes[0].method,'PATCH');assert.equal('작업내용' in writes[0].body,false);
 await page.locator('#memory-title').fill('다시 미저장');await page.locator('#reset-memory-button').click();
 assert.equal(await page.locator('#memory-title').inputValue(),'새 저장 제목');
 await page.locator('#memory-title').fill('상단 초안 유지');
 await page.locator('.memory-work-link').first().click();
 await page.waitForFunction(()=>document.querySelectorAll('.memory-point-stage img').length===3 && [...document.querySelectorAll('.memory-point-stage img')].every(i=>i.complete));
 assert.equal(await page.locator('.memory-point-figure').count(),4);
 assert.equal(await page.locator('.memory-point-figure').first().locator('img').count(),1);
 assert.equal(await page.locator('.memory-point-figure').first().locator('.memory-point-marker').count(),2);
 assert.match(await page.locator('#work-view-content').innerText(),/없는 포인트: 999/);
 assert.match(await page.locator('#work-view-content').innerText(),/마지막 <script>/);
 assert.equal(await page.locator('#work-view-content script').count(),0);
 assert.equal(await page.locator('#work-view-content').evaluate(el=>[...el.children].map(e=>e.className).join(',')), 'memory-work-text,memory-point-figure,memory-work-text,memory-point-figure,memory-work-text,memory-point-figure,memory-work-text,memory-point-figure,memory-work-text');
 if(process.env.MEMORY_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.MEMORY_SCREENSHOT_DIR,'work-detail.png')});
 await page.locator('.memory-point-marker').first().click();assert.match(await page.locator('.memory-point-note').first().innerText(),/주석 1/);
 for(const width of [1280,390]) {
  await page.setViewportSize({width,height:900});
  const ratio=await page.locator('.memory-point-stage').first().evaluate(stage=>{const r=stage.getBoundingClientRect(),m=stage.querySelector('button').getBoundingClientRect();return [(m.x+m.width/2-r.x)/r.width,(m.y+m.height/2-r.y)/r.height];});
  assert.ok(Math.abs(ratio[0]-.2)<.01);assert.ok(Math.abs(ratio[1]-.2)<.01);
 }
 await page.setViewportSize({width:1280,height:1000});
 await page.locator('#edit-memory-work').click();await page.locator('#work-summary').fill('작업만 수정');await page.locator('#save-memory-work').click();
 await page.waitForFunction(()=>document.querySelector('#memory-work-message').textContent==='작업내용을 저장했습니다.');
 await page.locator('#close-memory-work').click();
 assert.equal(await page.locator('#memory-title').inputValue(),'상단 초안 유지');
 assert.match(await page.locator('.memory-work-link').first().innerText(),/작업만 수정/);
 await page.locator('#reset-memory-button').click();assert.equal(await page.locator('#memory-title').inputValue(),'새 저장 제목');
 await page.locator('.memory-work-link').first().click();page.once('dialog',d=>d.accept());await page.locator('#delete-memory-work').click();
 await page.waitForFunction(()=>!document.querySelector('#memory-work-dialog').open);
 assert.equal(await page.locator('.memory-work-link').count(),1);
 assert.match(await page.locator('.memory-work-link').innerText(),/전원부 전압 측정/);
 // Canceling whole-memo deletion must not send a request.
 const before=writes.length;page.once('dialog',d=>d.dismiss());await page.locator('#delete-memory-button').click();assert.equal(writes.length,before);
 await page.locator('#memory-search-mode').uncheck();
 assert.equal(await page.locator('#memory-work-search').isVisible(),false);
 assert.equal(await page.locator('#memory-image-search').isVisible(),true);
 await page.locator('#memory-image-id').fill('12');
 await page.locator('#memory-image-id').press('Enter');
 await page.waitForSelector('#memory-image-search-result img');
 assert.equal(await page.locator('#memory-image-search-result img').count(),1);
 assert.equal(await page.locator('#memory-image-search-result .memory-point-marker').count(),4);
 latest={image_id:13,revision:1};
 await page.waitForFunction(()=>document.querySelector('#memory-latest-result img')?.alt==='이미지 13');
 assert.equal(await page.locator('#memory-image-search-result img').getAttribute('alt'),'이미지 12');
 await page.locator('#memory-search-mode').check();
 assert.equal(await page.locator('#memory-work-search').isVisible(),true);
 assert.equal(await page.locator('#memory-latest-result img').isVisible(),true);
 latest={image_id:12,revision:2};
 await page.waitForFunction(()=>document.querySelector('#memory-latest-result img')?.alt==='이미지 12');
 assert.deepEqual(errors,[]);
 console.log('PASS: new/view UI, cancel baselines, separate saves/deletes, reference order, missing references, annotations, responsive coordinates, HTML escaping');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
