from pathlib import Path
src=Path('M4C/Scripts/m4c-e2e.mjs').read_text(encoding='utf-8-sig')
src=src.replace("import { spawn }", "import { spawn, execFileSync }")
before,body=src.split("  if (phase === 'chapter') {",1)
rest=body[body.index('  results.pages = pages();'):]
before=before.replace("  results.coldLoadMs = await loadPage();","""  await rpc('Page.bringToFront');
  await rpc('Page.addScriptToEvaluateOnNewDocument', {source: `
   window.nativeEvents=[];
   for(const type of ['compositionstart','compositionupdate','compositionend','beforeinput','input']){
     document.addEventListener(type,e=>window.nativeEvents.push({type,data:e.data}),true);
   }
   let draws=0;
   const proto=WebGL2RenderingContext.prototype;
   for(const name of ['drawArrays','drawElements','drawArraysInstanced','drawElementsInstanced']){
     const fn=proto[name];proto[name]=function(...args){draws++;return fn.apply(this,args)};
   }
   window.sampleFrames=(duration)=>new Promise(done=>{
     let start=performance.now(),last=draws,active=[],ticks=0;
     function tick(now){ticks++;if(draws!==last){active.push(now);last=draws}
       if(now-start<duration){requestAnimationFrame(tick);return}
       const gaps=active.slice(1).map((v,i)=>v-active[i]).sort((a,b)=>a-b);
       done({ms:now-start,ticks,drawFrames:active.length,drawFPS:active.length*1000/(now-start),
             p95GapMs:gaps[Math.floor(gaps.length*0.95)],visibility:document.visibilityState});
     }requestAnimationFrame(tick);
   });
  `});
  results.coldLoadMs = await loadPage();
  results.frameSample=(await rpc('Runtime.evaluate',{expression:'window.sampleFrames(10000)',awaitPromise:true,returnByValue:true})).result.value;""")
insert="""
  if(phase==='gpu') {
    await clickAt(await hudPoint(-55,78));
    await rpc('Page.bringToFront');
    const native=action=>JSON.parse(execFileSync('python',['M4CG/native-input.py',String(chrome.pid),action],{encoding:'utf8'}));
    results.physicalInput=native('type');
    await screenshot('03-native-input');
    if(results.physicalInput.sent.length===5) {
      results.confirm=native('confirm');
      await screenshot('04-after-selection');
      await key('Enter');
      await delay(700);
    }
    results.nativeEvents=await evaluate('window.nativeEvents');
    results.nativePage=lastPage();
    await key('Escape');
    results.afterEscape=lastPage();
  }
"""
Path('Builds/M4CG-Audit/runtime.mjs').write_text(before+insert+rest,encoding='utf-8')
