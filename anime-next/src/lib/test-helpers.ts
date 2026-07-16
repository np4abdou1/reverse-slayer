const tests: Array<{ name: string; fn: () => void | Promise<void> }> = [];
let currentDescribe = '';

export function describe(name: string, fn: () => void) {
  currentDescribe = name;
  fn();
  currentDescribe = '';
}

export function it(name: string, fn: () => void | Promise<void>) {
  tests.push({ name: currentDescribe ? `${currentDescribe} > ${name}` : name, fn });
}

export function expect<T>(actual: T) {
  return {
    toBe(expected: T) {
      if (actual !== expected) {
        throw new Error(`Expected ${JSON.stringify(expected)} but got ${JSON.stringify(actual)}`);
      }
    },
    toEqual(expected: T) {
      const a = JSON.stringify(actual);
      const e = JSON.stringify(expected);
      if (a !== e) {
        throw new Error(`Expected ${e} but got ${a}`);
      }
    },
  };
}

export function beforeAll(_fn: () => void) {}
export function afterAll(_fn: () => void) {}

async function run() {
  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      await test.fn();
      console.log(`  ✓ ${test.name}`);
      passed++;
    } catch (e: any) {
      console.log(`  ✗ ${test.name}`);
      console.log(`    ${e.message}`);
      failed++;
    }
  }

  console.log(`\n${passed} passed, ${failed} failed, ${tests.length} total`);
  if (failed > 0) process.exit(1);
}

setTimeout(run, 0);
