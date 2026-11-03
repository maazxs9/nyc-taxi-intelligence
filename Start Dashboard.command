#!/bin/zsh
cd -- "${0:A:h}"
echo 'Open http://127.0.0.1:8766 in your browser. Press Ctrl+C to stop.'
node scripts/serve.mjs
