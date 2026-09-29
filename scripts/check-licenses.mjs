#!/usr/bin/env node
// Licence gate for an npm package (CLAUDE.md "라이선스 규칙").
// Usage: node scripts/check-licenses.mjs <package-dir>
//
// - Shipped code (the `dependencies` closure) must match the allowlist exactly.
// - Build/dev tooling (everything else in node_modules) never ships; it only fails on
//   copyleft licences (GPL/AGPL/LGPL/SSPL/EUPL), which could leak into build outputs.
// Reviewed per-package exceptions live in scripts/license-exceptions.json.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ALLOWED = new Set([
  'MIT',
  'MIT-0',
  'Apache-2.0',
  'BSD-2-Clause',
  'BSD-3-Clause',
  '0BSD',
  'ISC',
  'Zlib',
  'CC0-1.0',
  'OFL-1.1',
  'Unlicense',
]);
const COPYLEFT = /\b(A?GPL|LGPL|SSPL|EUPL|CPAL|OSL)\b/i;

const root = process.argv[2] ?? '.';
const exceptionsFile = join(dirname(fileURLToPath(import.meta.url)), 'license-exceptions.json');
const exceptions = existsSync(exceptionsFile)
  ? JSON.parse(readFileSync(exceptionsFile, 'utf-8'))
  : {};

/** Evaluates simple SPDX expressions: OR needs one allowed term, AND needs all. */
function allowed(expr) {
  const e = expr.replace(/[()]/g, ' ').trim();
  if (/ OR /i.test(e)) return e.split(/ OR /i).some((t) => allowed(t));
  if (/ AND /i.test(e)) return e.split(/ AND /i).every((t) => allowed(t));
  return ALLOWED.has(e.replace(/\+$/, ''));
}

function copyleftOnly(expr) {
  // "MIT OR GPL-2.0" is fine: we can pick MIT.
  if (/ OR /i.test(expr)) return expr.split(/ OR /i).every((t) => copyleftOnly(t));
  return COPYLEFT.test(expr);
}

function licenseOf(pkg) {
  if (typeof pkg.license === 'string') return pkg.license;
  if (pkg.license?.type) return pkg.license.type;
  if (Array.isArray(pkg.licenses)) return pkg.licenses.map((l) => l.type ?? l).join(' OR ');
  return 'UNKNOWN';
}

/** Resolves a dependency the way Node does: nearest node_modules walking up. */
function resolveDir(fromDir, name) {
  let dir = fromDir;
  for (;;) {
    const candidate = join(dir, 'node_modules', name);
    if (existsSync(join(candidate, 'package.json'))) return candidate;
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

function readPkg(dir) {
  return JSON.parse(readFileSync(join(dir, 'package.json'), 'utf-8'));
}

/** Directories of every package reachable from `dependencies` (the shipped closure). */
function productionClosure(rootDir) {
  const seen = new Set();
  const stack = Object.keys(readPkg(rootDir).dependencies ?? {}).map((n) => [rootDir, n]);
  while (stack.length) {
    const [from, name] = stack.pop();
    const dir = resolveDir(from, name);
    if (!dir || seen.has(dir)) continue;
    seen.add(dir);
    const pkg = readPkg(dir);
    for (const dep of Object.keys({ ...pkg.dependencies, ...pkg.optionalDependencies })) {
      stack.push([dir, dep]);
    }
  }
  return seen;
}

function* allPackages(dir) {
  const nm = join(dir, 'node_modules');
  if (!existsSync(nm)) return;
  for (const entry of readdirSync(nm)) {
    if (entry.startsWith('.')) continue;
    const names = entry.startsWith('@')
      ? readdirSync(join(nm, entry)).map((n) => `${entry}/${n}`)
      : [entry];
    for (const name of names) {
      const pkgDir = join(nm, name);
      if (!existsSync(join(pkgDir, 'package.json'))) continue;
      yield pkgDir;
      yield* allPackages(pkgDir);
    }
  }
}

const own = readPkg(root);
const prod = productionClosure(root);
const violations = new Set();
let count = 0;
for (const dir of allPackages(root)) {
  const pkg = readPkg(dir);
  if (!pkg.name || !pkg.version) continue;
  count++;
  const license = licenseOf(pkg);
  if (exceptions[pkg.name]) continue;
  const shipped = prod.has(dir);
  const ok = shipped ? allowed(license) : !copyleftOnly(license) && license !== 'UNKNOWN';
  if (!ok) violations.add(`${shipped ? '[shipped]' : '[dev]'} ${pkg.name}@${pkg.version}: ${license}`);
}

if (violations.size > 0) {
  console.error(`[check-licenses] ${own.name}: ${violations.size} package(s) rejected:`);
  for (const v of [...violations].sort()) console.error(`  - ${v}`);
  console.error('Replace them, or add a reviewed entry to scripts/license-exceptions.json.');
  process.exit(1);
}
console.log(`[check-licenses] ${own.name}: ${count} packages OK (${prod.size} shipped, strict allowlist)`);
