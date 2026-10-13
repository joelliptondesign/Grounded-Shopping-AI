const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {validate} = require('../../frontend/preview-contract.js');
function app(html, preview=false) {
 const context = { document:{documentElement:{setAttribute(){}}}, URLSearchParams, location:{search:preview?'?preview=1':'',origin:'http://localhost'}, React:{createRef:()=>({current:null})}, DCLogic:class {setState(x){this.state={...this.state,...(typeof x==='function'?x(this.state):x)};}}, setTimeout,clearTimeout,fetch:()=>{throw Error('Unexpected network');}, parent:{postMessage(){}}, addEventListener(){},removeEventListener(){} };
 vm.createContext(context);
 vm.runInContext(fs.readFileSync('frontend/renderer.js','utf8'),context);
 vm.runInContext(fs.readFileSync('frontend/preview-contract.js','utf8'),context);
 const script=html.match(/<script type="text\/x-dc"[^>]*>([\s\S]*?)<\/script>/)[1];
 vm.runInContext(script+'\n globalThis.instance = new Component();',context);
 context.instance.testParent = context.parent;
 return context.instance;
}
const current=fs.readFileSync('frontend/Rufus Shopping Agent.dc.html','utf8');
// Captured from d56e0ea before renderer extraction, excluding callbacks.
const baseline=JSON.parse(fs.readFileSync('tests/frontend/render-baseline.json','utf8'));
const clean=x=>JSON.parse(JSON.stringify(x));
test('normal rendering retains baseline values across all block kinds',()=>{
 const after=app(current);
 const blocks=[{kind:'user',text:'Hello'},{kind:'recs'},{kind:'compare',pair:['polar','zenith']},{kind:'suggest'},{kind:'service'},{kind:'feedback'},{kind:'progress',active:1},{kind:'dots'},{kind:'text',parts:[{t:'Hello',b:true}]}];
 after.state.blocks=blocks;
 const actual=clean(after.renderVals()); delete actual.previewReadOnly;
 assert.deepEqual(actual,baseline);
 after.renderVals().blocks[5].onUp(); assert.equal(after.state.feedback[5],'up');
 after.renderVals().blocks[5].onUp(); assert.equal(after.state.feedback[5],null);
});
test('preview rejects missing data and never uses demo defaults',()=>{
 for(const blocks of [[{kind:'recs'}],[{kind:'suggest'}],[{kind:'compare',pair:['a','b'],names:['A','B']}],[{kind:'recs',more:false,items:[{id:'missing',role:'Choice',why:'Reason'}]}]]) assert.throws(()=>validate({id:'bad',products:[],blocks}));
 assert.deepEqual(validate({id:'empty',products:[],blocks:[{kind:'suggest',items:[]}]}).blocks[0].items,[]);
});
test('preview actions, reset and direct API seams cannot issue requests',async()=>{
 const a=app(current,true), events=[]; a.previewAction=(action,details)=>events.push({action,details});
 a.loadPreview({id:'reply',products:[],blocks:[{kind:'suggest',items:['Compare']},{kind:'feedback'}]});
 a.renderVals().blocks[0].suggestions[0].onPick(); a.renderVals().blocks[1].onDown();
 a.addToCart('x'); a.moreFor('value',{}); a.submit('hello'); a.selectMode('live'); a.endLiveSession();
 assert.equal(a.state.mode,'demo'); assert.equal(a.state.blocks.length,2);
 for(const fn of [()=>a.liveSessionId(),()=>a.submitLiveTurn('x'),()=>a.submitLiveMore('x',[]),()=>a.streamLiveTurn('x',()=>{})]) await assert.rejects(fn,/disabled/);
 assert.throws(()=>a.postLiveTurn('x','x'),/disabled/);
 a.resetConversation(); assert.equal(a.state.blocks.length,0); assert.deepEqual(clean(a.state.cart),{});
 a.loadPreview({id:'bad',products:[],blocks:[{kind:'suggest'}]}); assert.match(a.state.blocks[0].parts[0].t,/Preview error/);
 assert(events.some(e=>e.action==='reply'));
});

test('preview bridge accepts only its same-origin parent',()=>{
 const a=app(current,true); a.componentDidMount();
 let loads=0; a.loadPreview=()=>loads++;
 const example={id:'x',products:[],blocks:[]};
 // Use the exact parent/origin captured by the mount, exposed through a test event.
 const handler=a.previewMessage;
 handler({source:{},origin:'http://localhost',data:{type:'rufus-preview:load',example}});
 handler({source:a.testParent,origin:'http://elsewhere',data:{type:'rufus-preview:load',example}});
 assert.equal(loads,0);
 handler({source:a.testParent,origin:"http://localhost",data:{type:"rufus-preview:load",example}});
 assert.equal(loads,1);
});

test('preview startup can be probed again without loading data or contacting shopping APIs',()=>{
 const a=app(current,true),events=[];a.previewAction=(action,details)=>events.push({action,details});a.componentDidMount();let loads=0;a.loadPreview=()=>loads++;
 const ping={type:'rufus-preview:ping'};a.previewMessage({source:{},origin:'http://localhost',data:ping});a.previewMessage({source:a.testParent,origin:'http://elsewhere',data:ping});assert.equal(events.length,1);
 a.previewMessage({source:a.testParent,origin:'http://localhost',data:ping});a.previewMessage({source:a.testParent,origin:'http://localhost',data:ping});assert.equal(events.length,3);assert(events.every(e=>e.action==='ready'));assert.equal(loads,0);
});
