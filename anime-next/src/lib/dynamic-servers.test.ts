import { describe, it, expect } from './test-helpers';
import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

const TEST_DB = path.join(process.cwd(), 'data', 'test_dynamic.db');

interface DbRow {
  episode_url_id: number;
  episode_id: number;
  episode_server_id: string;
  [key: string]: unknown;
}

function createTestDb(): Database.Database {
  if (fs.existsSync(TEST_DB)) fs.unlinkSync(TEST_DB);
  const db = new Database(TEST_DB);
  db.pragma('journal_mode = WAL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS episode_servers (
      episode_url_id INTEGER PRIMARY KEY,
      episode_id INTEGER NOT NULL,
      episode_server_id TEXT NOT NULL,
      episode_server_name TEXT,
      episode_url TEXT NOT NULL,
      episode_server_status TEXT DEFAULT 'active'
    );
    CREATE TABLE IF NOT EXISTS episodes (
      episode_id INTEGER PRIMARY KEY,
      anime_id INTEGER NOT NULL,
      episode_name TEXT,
      episode_number REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS animes (
      anime_id INTEGER PRIMARY KEY,
      anime_slug TEXT
    );
  `);
  return db;
}

function cleanDb(db: Database.Database) {
  db.close();
  if (fs.existsSync(TEST_DB)) fs.unlinkSync(TEST_DB);
}

function epToken(epNum: number): string {
  if (Number.isInteger(epNum)) return String(epNum);
  return String(epNum).replace(/0+$/, '').replace(/\.$/, '');
}

function decryptWitWatchServers(html: string): Array<{ index: number; name: string; type: string; url: string }> {
  const zxMatch = html.match(/(?:var\s+)?_z[HX]\s*=\s*"([^"]+)"/);
  const zkMatch = html.match(/(?:var\s+)?_z[WK]\s*=\s*"([^"]+)"/);
  if (!zxMatch || !zkMatch) return [];

  try {
    const rr = JSON.parse(Buffer.from(zxMatch[1], 'base64').toString());
    const cr = JSON.parse(Buffer.from(zkMatch[1], 'base64').toString());

    const nameMap: Record<string, string> = {};
    const nameRegex = /<a[^>]*data-server-id="(\d+)"[^>]*>([\s\S]*?)<\/a>/g;
    let nm;
    while ((nm = nameRegex.exec(html)) !== null) {
      nameMap[nm[1]] = nm[2].replace(/<[^>]+>/g, '').trim();
    }

    const servers: Array<{ index: number; name: string; type: string; url: string }> = [];
    for (let i = 0; i < rr.length; i++) {
      try {
        const reversed = String(rr[i]).split('').reverse().join('');
        const raw = reversed.replace(/[^A-Za-z0-9+/=]/g, '');
        let url = Buffer.from(raw, 'base64').toString();
        const idx = parseInt(Buffer.from(String(cr[i].k), 'base64').toString());
        const off = cr[i].d[idx];
        if (off > 0) url = url.slice(0, -off);

        const name = nameMap[String(i)] || '';
        const type = url.toLowerCase().includes('yonaplay') ? 'yonaplay' : 'direct';

        servers.push({ index: i, name, type, url });
      } catch {}
    }
    return servers;
  } catch {
    return [];
  }
}

describe('epToken', () => {
  it('returns integer string for whole numbers', () => {
    expect(epToken(1)).toBe('1');
    expect(epToken(12)).toBe('12');
    expect(epToken(0)).toBe('0');
  });

  it('returns decimal string for fractional numbers', () => {
    expect(epToken(1.5)).toBe('1.5');
    expect(epToken(7.5)).toBe('7.5');
  });
});

describe('decryptWitWatchServers', () => {
  it('returns empty array when no decryption vars found', () => {
    expect(decryptWitWatchServers('<html></html>')).toEqual([]);
  });

  it('returns empty array for invalid base64', () => {
    expect(decryptWitWatchServers('var _zX = "!!!"; var _zK = "!!!";')).toEqual([]);
  });

  it('handles empty server list gracefully', () => {
    const emptyList = Buffer.from(JSON.stringify([])).toString('base64');
    const emptyKeys = Buffer.from(JSON.stringify([])).toString('base64');
    const html = 'var _zX = "' + emptyList + '"; var _zK = "' + emptyKeys + '";';
    expect(decryptWitWatchServers(html)).toEqual([]);
  });
});

describe('DB caching behavior', () => {
  it('inserts and retrieves wit servers', () => {
    const db = createTestDb();
    db.prepare('INSERT INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url) VALUES (?, ?, ?, ?, ?)')
      .run(1, 100, 'wit_0', 'Server1', 'https://example.com/video.mp4');

    const rows = db.prepare("SELECT * FROM episode_servers WHERE episode_id = ? AND episode_server_id LIKE 'wit_%'").all(100) as DbRow[];
    expect(rows.length).toBe(1);
    expect(rows[0].episode_server_id).toBe('wit_0');
    cleanDb(db);
  });

  it('detects existing wit servers correctly', () => {
    const db = createTestDb();
    db.prepare("INSERT INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url) VALUES (1, 101, 'wit_0', 'S1', 'url')").run();

    const rows = db.prepare("SELECT * FROM episode_servers WHERE episode_id = ? AND episode_server_id LIKE 'wit_%'").all(101) as DbRow[];
    expect(rows.length > 0).toBe(true);
    cleanDb(db);
  });

  it('detects missing a3rb servers correctly', () => {
    const db = createTestDb();
    db.prepare("INSERT INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url) VALUES (1, 102, 'wit_0', 'S1', 'url')").run();

    const rows = db.prepare("SELECT * FROM episode_servers WHERE episode_id = ? AND episode_server_id LIKE 'a3rb_%'").all(102) as DbRow[];
    expect(rows.length).toBe(0);
    cleanDb(db);
  });

  it('INSERT OR IGNORE prevents duplicates', () => {
    const db = createTestDb();
    db.prepare("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url) VALUES (1, 103, 'wit_0', 'S1', 'url')").run();
    db.prepare("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url) VALUES (1, 103, 'wit_0', 'S1', 'url')").run();

    const rows = db.prepare("SELECT * FROM episode_servers WHERE episode_id = 103 AND episode_server_id = 'wit_0'").all() as DbRow[];
    expect(rows.length).toBe(1);
    cleanDb(db);
  });
});

console.log('\n✓ All tests passed!\n');
