#!/usr/bin/env node
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const pythonScript = join(__dirname, 'FIXED-ANSLAYER-DUMBER.py');
const args = process.argv.slice(2).join(' ');

try {
  execSync(`python3 "${pythonScript}" ${args}`, { stdio: 'inherit' });
} catch (err) {
  process.exit(1);
}
