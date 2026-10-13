import fs from 'node:fs/promises';
import path from 'node:path';
export const localRuntimeFiles={
 '/preview/react.js':'react/umd/react.production.min.js',
 '/preview/react-dom.js':'react-dom/umd/react-dom.production.min.js',
 '/preview/babel.js':'@babel/standalone/babel.min.js',
 '/preview/nunito.woff2':'@fontsource/nunito/files/nunito-latin-900-italic.woff2'
};
export const runtimeResources=`window.__resources=Object.assign({},window.__resources,${JSON.stringify({
 'https://unpkg.com/react@18.3.1/umd/react.production.min.js':'/preview/react.js',
 'https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js':'/preview/react-dom.js',
 'https://unpkg.com/@babel/standalone@7.29.0/babel.min.js':'/preview/babel.js'
})});`;
export function localPreviewHtml(html){
 return html.replace('<head>','<head><script src="/preview/runtime-resources.js"></script>')
 .replace(/<link[^>]+href="https:\/\/fonts\.googleapis\.com[^>]+>/g,'<style>@font-face{font-family:Nunito;font-style:italic;font-weight:900;font-display:swap;src:url(/preview/nunito.woff2) format("woff2")}</style>');
}
export async function copyPreviewRuntime(output){
 for(const [url,source] of Object.entries(localRuntimeFiles))await fs.copyFile(path.join(import.meta.dirname,'node_modules',source),path.join(output,url.split('/').pop()));
 await fs.writeFile(path.join(output,'runtime-resources.js'),runtimeResources);
}
