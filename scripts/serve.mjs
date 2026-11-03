import http from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../website/dist');
const types={'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json','.geojson':'application/geo+json','.svg':'image/svg+xml','.zip':'application/zip'};
const server=http.createServer(async(req,res)=>{
  try {
    const requested=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    const file=path.resolve(root,'.'+(requested==='/'?'/index.html':requested));
    if(!file.startsWith(root+path.sep))throw new Error('Invalid path');
    const data=await readFile(file);
    res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-cache'});
    res.end(data);
  }catch{res.writeHead(404);res.end('Not found');}
});
server.listen(8766,'127.0.0.1',()=>console.log('Local: http://127.0.0.1:8766'));
